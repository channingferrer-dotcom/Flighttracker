import re
import logging

logger = logging.getLogger(__name__)


def parse_price(price_str):
    """Convert a price string like '$1,234' or '1234' to a float."""
    if price_str is None:
        return None
    cleaned = re.sub(r'[^\d.]', '', str(price_str))
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


def search_flights(route):
    """
    Search Google Flights for the lowest price on a given route using fast-flights.
    Supports one-way, round-trip, and multi-leg trips.

    Returns a dict with price and flight details, or None if the search failed.
    """
    try:
        from fast_flights import FlightData, Passengers, create_filter, get_flights

        trip_type = route.get('trip_type', 'one-way')
        adults = int(route.get('adults', 1))
        seat = route.get('seat_class', 'economy')

        # Build flight legs
        flight_data = [
            FlightData(
                date=route['departure_date'],
                from_airport=route['origin'].upper(),
                to_airport=route['destination'].upper(),
            )
        ]

        # Add return leg for round trips
        if trip_type == 'round-trip' and route.get('return_date'):
            flight_data.append(
                FlightData(
                    date=route['return_date'],
                    from_airport=route['destination'].upper(),
                    to_airport=route['origin'].upper(),
                )
            )

        # Multi-leg support: legs stored as JSON string in route['extra_legs']
        if trip_type == 'multi-leg' and route.get('extra_legs'):
            import json
            try:
                legs = json.loads(route['extra_legs'])
                for leg in legs:
                    flight_data.append(
                        FlightData(
                            date=leg['date'],
                            from_airport=leg['origin'].upper(),
                            to_airport=leg['destination'].upper(),
                        )
                    )
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Could not parse extra_legs for route {route.get('id')}: {e}")

        fast_trip = 'round-trip' if trip_type == 'round-trip' else 'one-way'

        filter_obj = create_filter(
            flight_data=flight_data,
            trip=fast_trip,
            seat=seat,
            passengers=Passengers(adults=adults),
        )

        result = get_flights(filter_obj)

        if not result or not result.flights:
            logger.warning(
                f"No flights returned for {route['origin']} → {route['destination']} on {route['departure_date']}"
            )
            return None

        # Find the cheapest option
        best_flight = None
        best_price = float('inf')

        for flight in result.flights:
            price = parse_price(getattr(flight, 'price', None))
            if price and price < best_price:
                best_price = price
                best_flight = flight

        if not best_flight or best_price == float('inf'):
            logger.warning(f"Could not parse any prices for route {route.get('id')}")
            return None

        return {
            'price': best_price,
            'currency': 'USD',
            'airline': getattr(best_flight, 'name', '') or '',
            'duration': getattr(best_flight, 'duration', '') or '',
            'stops': str(getattr(best_flight, 'stops', '') or ''),
            'departure_time': getattr(best_flight, 'departure', '') or '',
            'arrival_time': getattr(best_flight, 'arrival', '') or '',
        }

    except ImportError:
        logger.error(
            "fast-flights is not installed. "
            "Add 'fast-flights' to requirements.txt and redeploy."
        )
        return None

    except Exception as e:
        logger.error(
            f"Scraper error for route {route.get('origin')} → {route.get('destination')}: {e}",
            exc_info=True,
        )
        return None
