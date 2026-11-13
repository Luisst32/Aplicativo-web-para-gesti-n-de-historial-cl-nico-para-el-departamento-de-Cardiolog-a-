from django.conf import settings
from django.core.files.uploadhandler import FileUploadHandler, StopUpload


class ImportSizeLimitHandler(FileUploadHandler):
    def __init__(self, request=None):
        super().__init__(request)
        self.total = 0
    def receive_data_chunk(self, raw_data, start):
        self.total += len(raw_data)
        if self.total > getattr(settings, 'IMPORT_MAX_BYTES', 50 * 1024 * 1024):
            raise StopUpload(connection_reset=True)
        return raw_data
    def file_complete(self, file_size):
        return None
