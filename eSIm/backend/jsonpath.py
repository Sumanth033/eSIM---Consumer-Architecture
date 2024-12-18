import jsonpath_ng


def js_path_find(js_dict, js_path):
    """Find/Match a JSON path within a given JSON-serializable dict.
    Args:
        js_dict : JSON-serializable dict to operate on
        js_path : JSONpath string
    Returns: Result of the JSONpath expression
    """
    jsonpath_expr = jsonpath_ng.parse(js_path)
    return jsonpath_expr.find(js_dict)


def js_path_modify(js_dict, js_path, new_val):
    """Find/Match a JSON path within a given JSON-serializable dict.
    Args:
        js_dict : JSON-serializable dict to operate on
        js_path : JSONpath string
        new_val : New value for field in js_dict at js_path
    """
    jsonpath_expr = jsonpath_ng.parse(js_path)
    jsonpath_expr.find(js_dict)
    jsonpath_expr.update(js_dict, new_val)
