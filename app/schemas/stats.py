from pydantic import BaseModel
from typing import List
from datetime import datetime


class ScrapingStats(BaseModel):
    todayJobs: int
    totalJobs: int
    successRate: float
    avgScrapeTime: str
    lastScrapeTime: str | None


class CategoryStats(BaseModel):
    name: str
    value: int


class SuccessRateStats(BaseModel):
    name: str
    value: float


class ScrapingHistory(BaseModel):
    id: int
    start_time: datetime
    end_time: datetime | None
    jobs_found: int
    status: str
    error: str | None


class DashboardStats(BaseModel):
    stats: ScrapingStats
    jobsByCategory: List[CategoryStats]
    successRate: List[SuccessRateStats]
    scrapingHistory: List[ScrapingHistory]
