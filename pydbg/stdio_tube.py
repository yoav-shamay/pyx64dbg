import os
import select
import errno

READ_CHUNK_SIZE = 8192

class StdioTube:
    """
    A class for handling the stdio of the debugged process through its PTY.
    Provides methods for sending and receiving data, as well as an interactive mode.
    """
    def __init__(self, pty):
        self.pty = pty
        self._buf = b""

    def _fill_buf(self, amt):
        """
        Fills buffer with at most amt bytes of data from the PTY.
        Returns True if data was read, False if not.
        """
        try:
            ready, _, _ = select.select([self.pty], [], [], 0)
            if not ready:
                return False
            
            chunk = os.read(self.pty, amt)
            self._buf += chunk
            return True
        except OSError as e:
            if e.errno == errno.EIO: # PTY EOF - raise EOFError to signal that the process has closed the PTY instead of OSError
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

    def recv(self, num_bytes=READ_CHUNK_SIZE):
        """
        Read up to num_bytes.
        If the process hasn't sent that much data yet, it will return whatever is available.
        """
        if not self._buf:
            read_cnt = max(num_bytes, READ_CHUNK_SIZE) # read at least READ_CHUNK_SIZE to avoid too many syscalls for small reads
            self._fill_buf(read_cnt)
        
        # Take up to num_bytes
        actual_take = min(len(self._buf), num_bytes)
        res = self._buf[:actual_take]
        self._buf = self._buf[actual_take:]
        return res

    def recvuntil(self, delimiter, drop=False):
        """
        Receives until the delimiter is found.
        If drop is True, the returned data will not include the delimiter.
        If the delimiter wasn't sent yet, it will return everything the process sent.
        """
        if isinstance(delimiter, str): delimiter = delimiter.encode()
        
        while delimiter not in self._buf:
            # Try to get more data
            read = self._fill_buf(READ_CHUNK_SIZE)
            if not read:
                # No data was read, which means we timed out. Return what we have.
                res = self._buf
                self._buf = b""
                return res

        # Extract from buffer
        idx = self._buf.index(delimiter)
        end_idx = idx + len(delimiter) if not drop else idx
        res = self._buf[:end_idx]
        self._buf = self._buf[idx + len(delimiter):]
        
        return res

    def recvline(self, drop=False):
        """
        Receives a line (until a newline character).
        If drop is True, the returned line will not include the newline character.
        If a full line hasn't been sent yet, it will return whatever is available.
        """
        return self.recvuntil(b'\n', drop)

    def recvall(self):
        """
        Reads all data sent by the process (until EOF or finished)
        """
        while True:
            try:
                success = self._fill_buf(READ_CHUNK_SIZE, timeout=None) # Block until data or death
                if not success:
                    # If _fill_buf returns False, it means we finished reading the data.
                    break
            except EOFError:
                break
        res = self._buf
        self._buf = b""
        return res
