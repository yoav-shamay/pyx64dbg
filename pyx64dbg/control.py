"""
Movement functions for the debugger.
Supports single-step, continue, step over and out.
Handles received signals.
Each function has a notify_updates parameter, which controls whether the update callbacks
are triggered after the movement.
This is needed because those functions are internally called by other movement functions,
and we only want to trigger updates after the debugger really finishes.
"""
from __future__ import annotations

from typing import TYPE_CHECKING
import pyx64dbg.os_interaction as os_interaction
import os
from capstone import CS_GRP_CALL, CsInsn
import signal
from pyx64dbg.number_types import CIntBase, UInt64

if TYPE_CHECKING:
    from pyx64dbg.debugger import Debugger

# constants for siginfo si_code for SIGTRAP, to differentiate between different reasons for hitting a breakpoint
TRAP_BRKPT = 1  # from hitting a breakpoint
TRAP_TRACE = 2  # from single stepping
SI_KERNEL = 128 # breakpoint stop might also have si_code of SI_KERNEL sometimes due to internal reasons


class Control:
    """
    This class handles the control of the debugged process.
    This includes functions related to movement, such as to step and continue execution.
    It also includes methods to kill the process and manage signals.
    """

    def __init__(self, debugger: Debugger):
        self._debugger: Debugger = debugger

    def _handle_signal(self, status: int) -> None:
        """
        An internal function to handle signals after a movement.
        It checks if the process exited, was stopped by a signal, or is still running, and updates the state accordingly.
        Needs to receieve whether the last movement was a single step from a breakpoint, to differentiate between our breakpoints and breakpoints that the process itself set
        """
        if os.WIFEXITED(status):  # process exited normally
            self._debugger.process_exited = True
            self._debugger.exit_code = os.WEXITSTATUS(status)
            self._debugger.error_signal = None
            self._debugger.stopped_signal = None
            self._debugger._on_exit()
        elif os.WIFSIGNALED(status):  # process was killed by a signal (not stopped)
            self._debugger.process_exited = True
            self._debugger.error_signal = os.WTERMSIG(status)
            self._debugger.exit_code = -self._debugger.error_signal  # python convention is to use negative exit code for signals
            self._debugger.stopped_signal = None
            self._debugger._on_exit()
        elif os.WIFSTOPPED(status):
            self._debugger.registers._refresh_registers()  # refresh registers after movement
            triggered_signal = os.WSTOPSIG(status)
            if triggered_signal == signal.SIGTRAP:
                # Might be a breakpoint or a single step, get the siginfo to find the reason
                siginfo = os_interaction.get_siginfo(self._debugger.child_pid)
                code = siginfo["si_code"]
                if code == TRAP_TRACE:
                    # a single step - we should ignore the signal
                    self._debugger.stopped_signal = None
                elif code in (TRAP_BRKPT, SI_KERNEL):
                    # a breakpoint - we should check if it's our breakpoint
                    rip = UInt64(self._debugger.registers.rip)
                    if rip - 1 in self._debugger.breakpoints.get_breakpoints():
                        # if the instruction at RIP - 1 is a breakpoint
                        # Then it's a breakpoint that we set and we should ignore the signal
                        # We need RIP - 1 as running CC would increment RIP by 1
                        self._debugger.stopped_signal = None
                        # We need to rewind RIP to the beginning of the breakpoint instruction
                        self._debugger.registers.set("rip", rip - 1, trigger_updates=False)  # don't trigger updates, the movement function will at the end
                    else:
                        # in any other case, it's a breakpoint that already existed in the binary.
                        # We shouldn't ignore the signal in this case
                        self._debugger.stopped_signal = triggered_signal
                else:
                    # any other code for SIGTRAP is unusual, but we should still treat it as a signal from the process itself
                    self._debugger.stopped_signal = triggered_signal

            else:
                # if it's not a sigtrap, it's from the process itself
                self._debugger.stopped_signal = triggered_signal
            # the stop callback will be triggered by the end of the movement function (as there can be further movements)
        else:
            raise RuntimeError(
                "Unexpected status after movement: " + str(status)
            )

    def _step_from_breakpoint(self, address: UInt64) -> None:
        """
        An internal function to single step when on a breakpoint.
        Temporarily removes the breakpoint, single steps, and then restores the breakpoint.
        This is needed as otherwise we'd just hit the same breakpoint again without executing any instructions, and we also need to restore the breakpoint immediately as we might hit it again.
        """
        self._debugger.breakpoints.remove_breakpoint(address, notify_updates=False)  # temporarily remove the breakpoint
        if self._debugger.stopped_signal is not None:
            # if we are currently stopped by a signal, we need to pass it to ptrace to continue execution, otherwise the process will just be stopped again by the same signal without executing any instructions
            os_interaction.single_step(
                self._debugger.child_pid, signal=self._debugger.stopped_signal
            )
            self._debugger.stopped_signal = None
        else:
            # otherwise just single step normally
            os_interaction.single_step(self._debugger.child_pid)
        _, status = os.waitpid(
            self._debugger.child_pid, 0
        )  # wait for child to raise a signal, which should be from single stepping
        self._handle_signal(status)
        if self._debugger.process_exited:
            # if the process exited while we were stepping from the breakpoint, we shouldn't try to restore the breakpoint, as it will cause an error
            return
        self._debugger.breakpoints.add_breakpoint(address, notify_updates=False)  # restore the breakpoint immediately

    def _notify_update_and_stop(self) -> None:
        """
        An internal helper method to trigger both the update callbacks and the stop callbacks (if the process didn't exit) after a movement.
        """
        self._debugger.update_callbacks.trigger()
        if not self._debugger.process_exited:
            # Trigger the stop callback only if the process didn't exit.
            self._debugger.stop_callbacks.trigger()

    def single_step(self, notify_updates: bool = True) -> None:
        """
        Steps a single instruction.
        """
        self._debugger._ensure_running()
        if notify_updates:
            self._debugger.busy_callbacks.trigger()
        rip = UInt64(self._debugger.registers.rip)  # we use UInt64 for addresses
        if rip in self._debugger.breakpoints.get_breakpoints():
            # if we are in a breakpoint we need to use the special method
            self._step_from_breakpoint(rip)
        else:
            if self._debugger.stopped_signal is not None:
                # if we are currently stopped by a signal, we need to pass it to ptrace to continue execution, otherwise the process will just be stopped again by the same signal without executing any instructions
                os_interaction.single_step(
                    self._debugger.child_pid, signal=self._debugger.stopped_signal
                )
                self._debugger.stopped_signal = None
            else:
                os_interaction.single_step(self._debugger.child_pid)
            _, status = os.waitpid(
                self._debugger.child_pid, 0
            )  # wait for child to raise a signal, which can be from hitting a breakpoint or exiting
            self._handle_signal(status)
        if notify_updates:
            self._notify_update_and_stop()

    def continue_execution(self, notify_updates: bool = True) -> None:
        """
        Continues execution until the next breakpoint or exit.
        """
        self._debugger._ensure_running()
        if notify_updates:
            self._debugger.busy_callbacks.trigger()
        rip = UInt64(self._debugger.registers.rip)
        if rip in self._debugger.breakpoints.get_breakpoints():
            self._step_from_breakpoint(rip)
            if (
                self._debugger.stopped_signal is not None
                or self._debugger.process_exited
            ):
                # if we are currently stopped by a signal or the process exited, we shouldn't continue execution, as the process is already stopped/exited, and continuing would cause an error
                if notify_updates:
                    # don't send a stop trigger as the process exited
                    self._debugger.update_callbacks.trigger()
                return
        if self._debugger.stopped_signal is not None:
            # if we are currently stopped by a signal, we need to pass it to ptrace to continue execution, otherwise the process will just be stopped again by the same signal without executing any instructions
            os_interaction.cont(self._debugger.child_pid, signal=self._debugger.stopped_signal)
            self._debugger.stopped_signal = None
        else:
            # otherwise continue normally
            os_interaction.cont(self._debugger.child_pid)
        _, status = os.waitpid(
            self._debugger.child_pid, 0
        )  # wait for child to raise a signal, which can be from hitting a breakpoint or exiting
        self._handle_signal(status)
        if notify_updates:
            self._notify_update_and_stop()

    def next(self, notify_updates: bool = True) -> None:
        """
        Steps over to the next instruction, stepping over function calls.
        """
        self._debugger._ensure_running()
        if notify_updates:
            self._debugger.busy_callbacks.trigger()
        rip: UInt64 = UInt64(self._debugger.registers.rip)  # we use UInt64 for addresses
        cur_instruction: CsInsn = self._debugger.memory.read_instruction(rip)  # read the instruction on current RIP
        if CS_GRP_CALL in cur_instruction.groups:
            # if the instruction is a call, set a temporary breakpoint on the next instruction and continue until hitting it (or other breakpoints)
            next_instruction_address = UInt64(
                cur_instruction.address + cur_instruction.size
            )  # represent addresses as UInt64 for consistency
            if next_instruction_address in self._debugger.breakpoints.get_breakpoints():
                # if there is already a breakpoint on the next instruction, skip adding the temporary breakpoint
                self.continue_execution(notify_updates=False)
                if notify_updates:
                    self._notify_update_and_stop()
                return
            self._debugger.breakpoints.add_breakpoint(  # add the temporary breakpoint on the next instruction
                next_instruction_address, notify_updates=False
            )
            self.continue_execution(notify_updates=False)
            if self._debugger.process_exited:
                # if the process exited while we were stepping over, we shouldn't try to remove the breakpoint, as it will cause an error
                # we should notify an update though, as process exiting is an update.
                if notify_updates:
                    self._debugger.update_callbacks.trigger()
                return
            self._debugger.breakpoints.remove_breakpoint(  # remove the temporary breakpoint, only if it didn't exit
                next_instruction_address, notify_updates=False
            )
        else:
            # if the instruction isn't a call, just single step
            self.single_step(notify_updates=False)
        if notify_updates:
            self._notify_update_and_stop()

    def finish(self, notify_updates: bool = True) -> None:
        """
        Steps out of the current function.
        """
        self._debugger._ensure_running()
        if notify_updates:
            self._debugger.busy_callbacks.trigger()
        # get the return address from the current stack frame
        current_frame = self._debugger.stack.current_frame()
        return_address = current_frame.saved_rip
        if return_address in self._debugger.breakpoints.get_breakpoints():
            # if there is already a breakpoint on the return address, skip adding the temporary breakpoint
            self.continue_execution(notify_updates=False)
            if notify_updates:
                self._notify_update_and_stop()
            return
        self._debugger.breakpoints.add_breakpoint(
            return_address, notify_updates=False
        )  # add a temporary breakpoint at the return address
        self.continue_execution(notify_updates=False)
        if not self._debugger.process_exited:
            # if the process exited while we were stepping out, we shouldn't try to remove the breakpoint, as it will cause an error
            self._debugger.breakpoints.remove_breakpoint(
                return_address, notify_updates=False
            )
        if notify_updates:
            self._notify_update_and_stop()

    def kill_process(self) -> None:
        """
        Kills the debugged process.
        """
        self._debugger._ensure_running()
        self._debugger.busy_callbacks.trigger()  # Trigger the busy callback as we wait for the process
        os_interaction.kill(self._debugger.child_pid)  # use os_interaction to kill the process
        _, status = os.waitpid(
            self._debugger.child_pid, 0
        )  # wait for child to raise a signal, which should be from killing the process
        self._handle_signal(status)
        self._debugger.update_callbacks.trigger()

    def surpass_signal(self) -> None:
        """
        Surpasses the current signal, allowing the process to continue execution without handling the signal.
        """
        self._debugger._ensure_running()
        if self._debugger.stopped_signal is None:
            raise ValueError("Not currently stopped by a signal")
        self._debugger.stopped_signal = None  # the signal is only saved in the stopped_signal field, so surpassing it is just setting that field to None
        self._debugger.update_callbacks.trigger()  # a signal surpass is an update so we need to trigger the callbacks
