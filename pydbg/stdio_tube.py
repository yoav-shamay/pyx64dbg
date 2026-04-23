import os
import select
import errno
import sys
import time

READ_CHUNK_SIZE = 8192

class StdioTube:
    """
    A class for handling the stdio of the debugged process through its PTY.
    Provides methods for sending and receiving data, as well as an interactive mode.
    """
    def __init__(self, pty):
        self.pty = pty
        self._buf = b""

    def _fill_buf(self, amt, timeout):
        """Fills buffer with at least amt bytes, or until timeout. Returns True if data was read, False on timeout."""
        try:
            ready, _, _ = select.select([self.pty], [], [], timeout)
            if not ready:
                return False
            
            chunk = os.read(self.pty, amt)
            self._buf += chunk
            return True
        except OSError as e:
            if e.errno == errno.EIO: # PTY EOF
                raise EOFError("Debugged process closed the PTY.")
            raise

    def send(self, data):
        if isinstance(data, str):
            data = data.encode()
        os.write(self.pty, data)

    def sendline(self, data):
        if isinstance(data, str):
            data = data.encode()
        self.send(data + b'\n')

    def recv(self, num_bytes=READ_CHUNK_SIZE, timeout=None):
        """
        Read up to num_bytes.
        Blocks until at least 1 byte is available, or timeout occurs.
        If timeout is None, blocks until data is available.
        """
        if not self._buf:
            read_cnt = max(num_bytes, READ_CHUNK_SIZE) # read at least READ_CHUNK_SIZE to avoid too many syscalls for small reads
            if not self._fill_buf(read_cnt, timeout):
                raise TimeoutError("Timed out waiting for data.")
        
        # Take up to num_bytes
        actual_take = min(len(self._buf), num_bytes)
        res = self._buf[:actual_take]
        self._buf = self._buf[actual_take:]
        return res

    def recvuntil(self, delimiter, timeout=None, drop=False):
        """
        Receives until the delimiter is found.
        If drop is True, the returned data will not include the delimiter.
        """
        if isinstance(delimiter, str): delimiter = delimiter.encode()
        
        start_time = time.time()
        while delimiter not in self._buf:
            # Calculate remaining time
            remaining = None
            if timeout is not None:
                remaining = timeout - (time.time() - start_time)
                if remaining <= 0:
                    raise TimeoutError(f"Delimiter {delimiter!r} not found in timeout")
            
            # Try to get more data
            if not self._fill_buf(READ_CHUNK_SIZE, remaining):
                raise TimeoutError(f"Delimiter {delimiter!r} not found (select timeout)")

        # Extract from buffer
        idx = self._buf.index(delimiter)
        end_idx = idx + len(delimiter) if not drop else idx
        res = self._buf[:end_idx]
        self._buf = self._buf[idx + len(delimiter):]
        
        return res

    def recvline(self, timeout=None, drop=False):
        return self.recvuntil(b'\n', timeout, drop)

    def recvall(self):
        """Reads until the process dies. Returns all collected data."""
        while True:
            try:
                self._fill_buf(READ_CHUNK_SIZE, timeout=None) # Block until data or death
            except EOFError:
                break
        res = self._buf
        self._buf = b""
        return res

    def interactive(self):
        """
        An interactive mode that connects the debugged process's stdio to the user's terminal, allowing real-time interaction.
        The user can exit interactive mode by pressing Ctrl+C.
        """
        stdin_fd = sys.stdin.fileno()
        print("[*] Interactive mode. Press Ctrl+C to return.")
        try:
            while True:
                r, _, _ = select.select([self.pty, stdin_fd], [], [])
                if self.pty in r:
                    data = os.read(self.pty, READ_CHUNK_SIZE)
                    if not data:
                        break
                    os.write(sys.stdout.fileno(), data)
                    sys.stdout.flush() # ensure output is shown immediately
                if stdin_fd in r:
                    data = os.read(stdin_fd, READ_CHUNK_SIZE)
                    if not data:
                        break
                    os.write(self.pty, data)
        except (EOFError, OSError, KeyboardInterrupt):
            # when reaching EOF, any read error, or user pressing Ctrl+C, we exit interactive mode
            pass
        finally:
            print("\n[*] Finished interactive mode.")