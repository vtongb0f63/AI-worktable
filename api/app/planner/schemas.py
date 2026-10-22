from datetime import date
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator, field_validator
from .domain import minutes


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class Timed(Input):
    title: str = Field(min_length=1, max_length=160)
    start_time: str | None = Field(default=None, pattern=r'^\d{2}:\d{2}$')
    end_time: str | None = Field(default=None, pattern=r'^\d{2}:\d{2}$')

    @model_validator(mode='after')
    def times(self):
        if bool(self.start_time) != bool(self.end_time):
            raise ValueError('请同时填写开始和结束时间')
        if self.start_time and minutes(self.start_time) >= minutes(self.end_time):
            raise ValueError('结束时间必须晚于开始时间')
        return self


class Task(Timed):
    date: date
    category: Literal['study', 'life', 'vocabulary', 'training'] = 'study'
    note: str = Field(default='', max_length=3000)
    status: Literal['pending', 'done', 'partial', 'skipped'] = 'pending'
    locked: bool = False
    due_on: date | None = None
    source_id: str | None = None


class Course(Timed):
    weekday: int = Field(ge=0, le=6)
    semester_start: date
    start_week: int = Field(default=1, ge=1, le=60)
    end_week: int = Field(default=20, ge=1, le=60)
    parity: Literal['all', 'odd', 'even'] = 'all'
    location: str = Field(default='', max_length=120)
    excluded_dates: list[date] = Field(default_factory=list, max_length=90)

    @model_validator(mode='after')
    def course_valid(self):
        if not self.start_time or self.start_week > self.end_week:
            raise ValueError('课程必须有上课时间与有效周次')
        return self


class Word(Input):
    term: str = Field(min_length=1, max_length=100)
    meaning: str = Field(default='', max_length=2000)
    part_of_speech: str = Field(default='', max_length=60)
    example: str = Field(default='', max_length=2000)
    source: str = Field(default='', max_length=1000)
    tags: str = Field(default='', max_length=200)


class Run(Input):
    date: date
    distance_km: float = Field(ge=0, le=250)
    duration_minutes: float = Field(ge=0, le=3000)
    effort: int = Field(ge=1, le=10)
    heart_rate: int | None = Field(default=None, ge=30, le=240)
    status: Literal['done', 'partial', 'skipped'] = 'done'
    task_id: str | None = None
    note: str = Field(default='', max_length=3000)
    discomfort: str = Field(default='', max_length=1000)
    splits: str = Field(default='', max_length=2000)

    @model_validator(mode='after')
    def running_values(self):
        if self.status != 'skipped' and (self.distance_km <= 0 or self.duration_minutes <= 0):
            raise ValueError('完成或部分完成训练时，请填写实际距离和用时')
        return self


class Settings(Input):
    semester_start: date | None = None
    periods: str = Field(default='第1节 08:00-08:45\n第2节 08:55-09:40', max_length=2000)
    wake_time: str = '07:00'
    sleep_time: str = '23:00'
    fixed_activities: str = Field(default='', max_length=2000)
    learning_goals: str = Field(default='', max_length=4000)
    weekly_study_hours: int = Field(default=15, ge=1, le=80)
    news_time: str = '07:00'
    weekly_time: str = '20:00'
    english_level: Literal['B1', 'B2', 'C1'] = 'B2'
    training_goal: str = Field(default='', max_length=1000)
    recent_performance: str = Field(default='', max_length=1000)
    weekly_mileage: str = Field(default='', max_length=1000)
    training_days: str = Field(default='', max_length=500)
    injury_notes: str = Field(default='', max_length=1000)

    @field_validator('wake_time', 'sleep_time', 'news_time', 'weekly_time')
    @classmethod
    def clock(cls, value):
        minutes(value)
        h, m = map(int, value.split(':'))
        return f'{h:02d}:{m:02d}'


class Revision(Input):
    version: int = Field(ge=1)
    data: dict


class JobInput(Input):
    kind: Literal['week_plan', 'training_plan', 'news', 'word_enrich', 'quiz', 'grade']
    payload: dict = Field(default_factory=dict)


class Answer(Input):
    answer: str = Field(min_length=1, max_length=3000)


class Review(Input):
    correct: bool


class Journal(Input):
    date: date
    text: str = Field(min_length=1, max_length=5000)


class Plan(Input):
    summary: str = Field(max_length=4000)
    tasks: list[Task] = Field(max_length=100)
    unscheduled: list[str] = Field(default_factory=list, max_length=50)


class QuizItem(Input):
    word_id: str
    mode: Literal['dictation', 'translation', 'choice']
    prompt: str = Field(min_length=1, max_length=2000)
    expected: str = Field(min_length=1, max_length=3000)
    options: list[str] = Field(default_factory=list, max_length=4)
    explanation: str = Field(default='', max_length=2000)

    @model_validator(mode='after')
    def options_valid(self):
        if self.mode == 'choice' and (len(set(self.options)) != 4 or self.expected not in self.options):
            raise ValueError('选择题需要四个不同选项且包含正确答案')
        return self


class QuizResult(Input):
    questions: list[QuizItem] = Field(min_length=1, max_length=20)


class Grade(Input):
    correct: bool
    feedback: str = Field(min_length=1, max_length=3000)
