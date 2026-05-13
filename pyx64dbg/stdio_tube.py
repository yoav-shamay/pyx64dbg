import os
import select
import errno

READ_CHUNK_SIZE = 8192

class StdioTube:
    """
    A class for handling the stdio of the debugged process through its PTY.
    Provides methods for sending and receiving data.
    """
    def __init__(self, pty: int) -> None:
        self._pty: int = pty
        self._buf: bytes = b""
        self._pty_closed = False

    def _fill_buf(self, amt: int) -> bool:
        """
        Fills buffer with at most amt bytes of data from the PTY.
        Returns True if data was read, False if not.
        """
        if self._pty_closed:
            return False # if we closed the PTY, we can't read any more data, so return False
        try:
            # use select to see if there's data to read, with timeout 0 so it doesn't block if there's no data
            ready, _, _ = select.select([self._pty], [], [], 0)
            if not ready: # no data exists to read
                return False
            # read the chunk and add it to the buffer
            chunk = os.read(self._pty, amt)
            self._buf += chunk
            return True
        except OSError as e:
            if e.errno == errno.EIO: # PTY EOF - raise EOFError to signal that the process has closed the PTY instead of OSError
                raise EOFError("Debugged process closed the PTY.")
            raise # otherwise just raise the original OSError

    def send(self, data: bytes | str) -> None:
        """
        Sends data to the process's stdio.
        Data can be either bytes or a string (if it's a string, it will be encoded to bytes using UTF-8).
        """
        if isinstance(data, str):
            data = data.encode()
        os.write(self._pty, data)

    def sendline(self, data: bytes | str) -> None:
        """
        Sends a line of data to the process's stdio.
        Equivalent to send with a newline character appended.
        Data can be either bytes or a string (if it's a string, it will be encoded to bytes using UTF-8).
        """
        if isinstance(data, str):
            data = data.encode()
        self.send(data + b'\n')

    def recv(self, num_bytes: int = READ_CHUNK_SIZE) -> bytes:
        """
        Read up to num_bytes.
        If the process hasn't sent that much data yet, it will return whatever is available.
        This can be empty.
        """
        # if the process hasn't sent enough data yet, try to read more until we have at least num_bytes in the buffer
        if len(self._buf) < num_bytes:
            read_cnt = max(num_bytes, READ_CHUNK_SIZE) # read at least READ_CHUNK_SIZE to avoid too many syscalls for small reads
            self._fill_buf(read_cnt)
        
        # Take up to num_bytes
        actual_take = min(len(self._buf), num_bytes)
        res = self._buf[:actual_take]
        self._buf = self._buf[actual_take:]
        return res

    def recvuntil(self, delimiter: str | bytes, drop: bool=False) -> bytes:
        """
        Receives until the delimiter is found.
        If drop is True, the returned data will not include the delimiter.
        If the delimiter wasn't sent yet, it will return everything the process sent.
        """
        if isinstance(delimiter, str): delimiter = delimiter.encode()
        
        while delimiter not in self._buf:
            # If we didn't get the delimiter yet, try to get more data
            read = self._fill_buf(READ_CHUNK_SIZE)
            if not read:
                # No data was read, which means we ran out of data before getting delimiter. Return what we have.
                res = self._buf
                self._buf = b""
                return res

        # Extract from buffer
        idx = self._buf.index(delimiter) # find the index of the delimiter
        end_idx = idx + len(delimiter) if not drop else idx # if drop is False, include the delimiter in the result, otherwise exclude it
        res = self._buf[:end_idx]
        self._buf = self._buf[idx + len(delimiter):] # crop the buffer to remove the returned data and the delimiter
        
        return res

    def recvline(self, drop: bool=False) -> bytes:
        """
        Receives a line (until a newline character).
        If drop is True, the returned line will not include the newline character.
        If a full line hasn't been sent yet, it will return whatever is available.
        Equivalent to recvuntil with delimiter of newline character.
        """
        return self.recvuntil(b'\n', drop)

    def recvall(self) -> bytes:
        """
        Reads all data sent by the process (until EOF or finished)
        """
        while True:
            # read until EOF / no more data
            try:
                success = self._fill_buf(READ_CHUNK_SIZE)
                if not success:
                    # If _fill_buf returns False, it means we finished reading the data.
                    break
            except EOFError:
                break
        # empty the buffer and return its content
        res = self._buf
        self._buf = b""
        return res

    def close_pty(self):
        """
        Closes the PTY file descriptor.
        Before reads everything to the buffer so the content isn't lost.
        """
        self._buf = self.recvall() # read everything to the buffer before closing to avoid losing data
        os.close(self._pty)
        self._pty_closed = True