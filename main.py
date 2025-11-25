from steely import Dan


@Dan.scan
def my_function(x, y):
    a = x + y
    b = [1, 2, 3]
    return a * len(b)

my_function(1, 2)