from datetime import datetime, timedelta
from typing import List
from .models import TimetableConfiguration
from timetable.models import PeriodDefinition

class TimetableConfigService:
    @staticmethod
    def generate_periods_for_config(config: TimetableConfiguration) -> List[PeriodDefinition]:
        """
        Auto-generate period definitions based on configuration
        """
        created_periods = []
        
        # Loop through each working day
        for day_num in config.working_days:
            # Start from day_start_time
            current_time = datetime.combine(datetime.today(), config.day_start_time)
            
            # Generate periods for this day
            for period_num in range(1, config.periods_per_day + 1):
                # Calculate start and end time
                start_time = current_time.time()
                
                # Add period duration
                end_datetime = current_time + timedelta(minutes=config.default_period_duration)
                end_time = end_datetime.time()
                
                # Create or get period definition
                period, created = PeriodDefinition.objects.get_or_create(
                    semester=config.semester,
                    period_number=period_num,
                    day_of_week=day_num,
                    defaults={
                        'start_time': start_time,
                        'end_time': end_time,
                        'duration_minutes': config.default_period_duration
                    }
                )
                
                if created:
                    created_periods.append(period)
                
                # Move to next period
                current_time = end_datetime
                
                # Add short break after each period (except last)
                if period_num < config.periods_per_day:
                    current_time += timedelta(minutes=config.short_break_duration)
                
                # Add lunch break after specified period
                if period_num == config.lunch_break_after_period:
                    current_time += timedelta(minutes=config.lunch_break_duration)
        
        return created_periods
