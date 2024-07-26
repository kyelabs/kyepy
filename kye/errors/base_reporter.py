class ErrorReporter:
    @property
    def had_error(self):
        raise NotImplementedError("report had_error is not implemented")

    def report(self):
        raise NotImplementedError("report method is not implemented")