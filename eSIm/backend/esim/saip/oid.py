
from functools import total_ordering
from typing import List, Union

@total_ordering
class OID:
    @staticmethod
    def intlist_from_str(instr: str) -> List[int]:
        return [int(x) for x in instr.split('.')]

    @staticmethod
    def str_from_intlist(intlist: List[int]) -> str:
        return '.'.join([str(x) for x in intlist])

    @staticmethod
    def highest_oid(oids: List['OID']) -> 'OID':
        return sorted(oids)[-1]

    def __init__(self, initializer: Union[List[int], str]):
        if isinstance(initializer, str):
            self.intlist = self.intlist_from_str(initializer)
        else:
            self.intlist = initializer

    def __str__(self) -> str:
        return self.str_from_intlist(self.intlist)

    def __repr__(self) -> str:
        return 'OID(%s)' % (str(self))

    def __eq__(self, other: 'OID'):
        return (self.intlist == other.intlist)

    def __ne__(self, other: 'OID'):
        # implement based on __eq__
        return not (self == other)

    def cmp(self, other: 'OID'):
        self_len = len(self.intlist)
        other_len = len(other.intlist)
        common_len = min(self_len, other_len)
        max_len = max(self_len, other_len)

        for i in range(0, max_len+1):
            if i >= self_len:
                # other list is longer
                return -1
            if i >= other_len:
                # our list is longer
                return 1
            if self.intlist[i] > other.intlist[i]:
                # our version is higher
                return 1
            if self.intlist[i] < other.intlist[i]:
                # other version is higher
                return -1
            # continue to next digit
        return 0

    def __gt__(self, other: 'OID'):
        if self.cmp(other) > 0:
            return True

    def prefix_match(self, oid_str: Union[str, 'OID']):
        """determine if oid_str is equal or below our OID."""
        return str(oid_str).startswith(str(self))


class eOID(OID):
    """OID helper for TCA eUICC prefix"""
    __prefix = [2,23,143,1]
    def __init__(self, initializer):
        if isinstance(initializer, str):
            initializer = self.intlist_from_str(initializer)
        super().__init__(self.__prefix + initializer)

MF = eOID("2.1")
DF_CD = eOID("2.2")
DF_TELECOM = eOID("2.3")
DF_TELECOM_v2 = eOID("2.3.2")
ADF_USIM_by_default = eOID("2.4")
ADF_USIM_by_default_v2 = eOID("2.4.2")
ADF_USIMopt_not_by_default = eOID("2.5")
ADF_USIMopt_not_by_default_v2 = eOID("2.5.2")
ADF_USIMopt_not_by_default_v3 = eOID("2.5.3")
DF_PHONEBOOK_ADF_USIM = eOID("2.6")
DF_GSM_ACCESS_ADF_USIM = eOID("2.7")
ADF_ISIM_by_default = eOID("2.8")
ADF_ISIMopt_not_by_default = eOID("2.9")
ADF_ISIMopt_not_by_default_v2 = eOID("2.9.2")
ADF_CSIM_by_default = eOID("2.10")
ADF_CSIM_by_default_v2 = eOID("2.10.2")
ADF_CSIMopt_not_by_default = eOID("2.11")
ADF_CSIMopt_not_by_default_v2 = eOID("2.11.2")
DF_EAP = eOID("2.12")
DF_5GS = eOID("2.13")
DF_5GS_v2 = eOID("2.13.2")
DF_5GS_v3 = eOID("2.13.3")
DF_5GS_v4 = eOID("2.13.4")
DF_SAIP = eOID("2.14")
DF_SNPN = eOID("2.15")
DF_5GProSe = eOID("2.16")
IoT_by_default = eOID("2.17")
IoTopt_not_by_default = eOID("2.18")
