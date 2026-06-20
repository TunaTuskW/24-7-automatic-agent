import requests
import json
from src.observability.logger import get_logger
from src.schemas.models import EconomicCalendar, EconomicEvent

logger = get_logger("forexfactory-adapter")

class ForexFactoryAdapter:
    def __init__(self):
        self.url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
        self.target_currencies = {"USD", "EUR", "JPY", "GBP", "CAD", "CHF", "AUD", "NZD", "CNY"}

    def fetch_calendar(self) -> EconomicCalendar:
        logger.info(f"Fetching Forex Factory calendar from {self.url}")
        try:
            resp = requests.get(self.url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            
            events = []
            for item in data:
                impact = item.get("impact", "")
                country = item.get("country", "")
                
                if impact == "High" and country in self.target_currencies:
                    events.append(EconomicEvent(
                        title=item.get("title", ""),
                        country=country,
                        date=item.get("date", ""),
                        impact=impact,
                        forecast=item.get("forecast", ""),
                        previous=item.get("previous", "")
                    ))
            
            logger.info(f"Parsed {len(events)} high-impact events for {self.target_currencies}")
            return EconomicCalendar(events=events)
            
        except Exception as e:
            logger.error(f"Failed to fetch Forex Factory calendar: {e}")
            return EconomicCalendar()
