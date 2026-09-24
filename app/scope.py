"""Conservative query-scope boundaries, not legal advice or a general classifier."""
import re


def personal_legal_entitlement(query: str) -> bool:
    """A company-policy snapshot cannot determine personal statutory rights.

    This intentionally refuses that class of question even if a location is
    provided. It does not block ordinary company-policy benefit questions or
    references to the Legal Department. Pattern coverage is limited and tested;
    the generator's broader grounding rules remain necessary.
    """
    text = query.casefold()
    legal = re.search(r"\b(?:legal(?:ly)?|statutory|law)\b", text)
    entitlement = re.search(r"\b(?:entitl\w*|rights?|minimum|guarantee\w*)\b", text)
    personal = re.search(r"\b(?:i|my|me|we|our|employees?|workers?)\b", text)
    return bool(legal and entitlement and personal)
