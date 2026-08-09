"""Static-first, course-aware code tutoring."""

from app.code_tutor.contracts import TutorResult
from app.code_tutor.service import CodeTutorService, render_tutor_result

__all__ = ["CodeTutorService", "TutorResult", "render_tutor_result"]
