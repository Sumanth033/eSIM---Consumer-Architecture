import abc
from osmocom.utils import b2h, h2b, Hexstr

from backend.utils import ResTuple

class SecureChannel(abc.ABC):
    @abc.abstractmethod
    def wrap_cmd_apdu(self, apdu: bytes) -> bytes:
        """Wrap Command APDU according to specific Secure Channel Protocol."""
        pass

    @abc.abstractmethod
    def unwrap_rsp_apdu(self, sw: bytes, rsp_apdu: bytes) -> bytes:
        """UnWrap Response-APDU according to specific Secure Channel Protocol."""
        pass

    def send_apdu_wrapper(self, send_fn: callable, pdu: Hexstr, *args, **kwargs) -> ResTuple:
        """Wrapper function to wrap command APDU and unwrap repsonse APDU around send_apdu callable."""
        pdu_wrapped = b2h(self.wrap_cmd_apdu(h2b(pdu)))
        res, sw = send_fn(pdu_wrapped, *args, **kwargs)
        res_unwrapped = b2h(self.unwrap_rsp_apdu(h2b(sw), h2b(res)))
        return res_unwrapped, sw
