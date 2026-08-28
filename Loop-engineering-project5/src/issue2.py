def get_first_n_elements(data, n):
    # BUG: Off-by-one error, returns n-1 elements
    return data[:n-1]
