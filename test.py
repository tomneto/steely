from steely import Logger

# Set global destination BEFORE creating logger instance
Logger.set_global_destination("./logs")

def save_function(*args, **kwargs):
    print(args, kwargs)


# Now create the logger - it will use the global destination
log = Logger('test', callback=save_function)

log.info("Hello world")
log.info("Hello world")
log.info("Hello world")