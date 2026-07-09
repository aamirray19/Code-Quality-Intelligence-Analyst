class AppError(Exception):
    """Raised for any Phase 1 validation or processing failure.

    Carries the fields needed to build the API's ErrorResponse body.
    
    Phase 4 error codes:
    - REPORT_NOT_FOUND: The requested report does not exist in the database.
    - SCAN_NOT_ANALYZED: The scan exists but has not been analyzed (phase_3_status != 'completed').
    - SCAN_NOT_COMPLETED: The scan exists but has not completed indexing (phase_2_status != 'completed').
    - CHAT_SESSION_NOT_FOUND: The requested chat session does not exist.
    """

    def __init__(self, error_code: str, message: str, http_status: int):
        self.error_code = error_code
        self.message = message
        self.http_status = http_status
        super().__init__(message)
