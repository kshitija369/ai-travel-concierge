# db.py
from google.cloud import firestore
from typing import Dict, Any, Optional, List, Union
import uuid
import os
from pydantic import BaseModel, Field, ValidationError
import logging
import traceback

# --- Pydantic Models ---
class AirportEvent(BaseModel):
  city_name: str = Field(description="Name of the departure city")
  airport_code: str = Field(description="IATA code of the departure airport")
  timestamp: str = Field(description="ISO 8601 departure or arrival date and time")

class AttractionEvent(BaseModel):
  event_type: str = Field(default="visit")
  description: str = Field(description="A title or description of the activity or the attraction visit")
  address: str = Field(description="Full address of the attraction")
  start_time: str = Field(description="Time in HH:MM format, e.g. 16:00")
  end_time: str = Field(description="Time in HH:MM format, e.g. 16:00")
  booking_required: bool = Field(default=False)
  price: Optional[str] = Field(default=None, description="Some events may cost money")

class FlightEvent(BaseModel):
  event_type: str = Field(default="flight")
  description: str = Field(description="A title or description of the Flight")
  booking_required: bool = Field(default=True)
  departure_airport: str = Field(description="Airport code, i.e. SEA")
  arrival_airport: str = Field(description="Airport code, i.e. SAN")
  flight_number: str = Field(description="Flight number, e.g. UA5678")
  boarding_time: str = Field(description="Time in HH:MM format, e.g. 15:30")
  seat_number: str = Field(description="Seat Row and Position, e.g. 32A")
  departure_time: str = Field(description="Time in HH:MM format, e.g. 16:00")
  arrival_time: str = Field(description="Time in HH:MM format, e.g. 20:00")
  price: Optional[str] = Field(default=None, description="Total air fare")
  booking_id: Optional[str] = Field(default=None, description="Booking Reference ID, e.g LMN-012-STU")

class HotelEvent(BaseModel):
  event_type: str = Field(default="hotel")
  description: str = Field(description="A name, title or a description of the hotel")
  address: str = Field(description="Full address of the attraction")
  check_in_time: str = Field(description="Time in HH:MM format, e.g. 16:00")
  check_out_time: str = Field(description="Time in HH:MM format, e.g. 15:30")
  room_selection: str
  booking_required: bool = Field(default=True)
  price: Optional[str] = Field(default=None, description="Total hotel price including all nights")
  booking_id: Optional[str] = Field(default=None, description="Booking Reference ID, e.g ABCD12345678")

class ItineraryDay(BaseModel):
  day_number: int = Field(description="Identify which day of the trip this represents, e.g. 1, 2, 3... etc.")
  date: str = Field(description="The Date this day YYYY-MM-DD format")
  events: List[Union[FlightEvent, HotelEvent, AttractionEvent]] = Field(default=[], description="The list of events for the day")

class Itinerary(BaseModel):
  trip_name: str = Field(default="Untitled Trip", description="Simple one liner to describe the trip. e.g. 'San Diego to Seattle Getaway'")
  start_date: str = Field(description="Trip Start Date in YYYY-MM-DD format")
  end_date: str = Field(description="Trip End Date in YYYY-MM-DD format")
  origin: str = Field(description="Trip Origin, e.g. San Diego")
  destination: str = Field(description="Trip Destination, e.g. Seattle")
  days: List[ItineraryDay] = Field(default_factory=list, description="The multi-days itinerary")

class StoredTripDocument(BaseModel):
  trip_id: str
  user_id: str
  trip_name: str
  start_date: Optional[str] = None
  end_date: Optional[str] = None
  itinerary_details: Itinerary
  created_at: Any
  status: str = "upcoming"
# --- End Pydantic Models ---

FIRESTORE_CLIENT: Optional[firestore.Client] = None
# Ensure this collection name is what you want in Firestore
TRIPS_COLLECTION = "user_trips_v2" # Changed to v2 for clarity if you had v1

def initialize_firestore_client(project_id: Optional[str] = None, database_id: str = "ai-agent-dev") -> bool:
  global FIRESTORE_CLIENT
  if FIRESTORE_CLIENT is None:
    try:
      effective_project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
      database_id = os.getenv("GOOGLE_FIRESTORE_DB")
      if not effective_project_id:
        logging.error("ERROR (db.py): GOOGLE_CLOUD_PROJECT not set for Firestore.")
        return False

      FIRESTORE_CLIENT = firestore.Client(project=effective_project_id, database=database_id)

      print(f"INFO (db.py): Firestore client initialized for project '{effective_project_id}' and database '{database_id}'.")
      return True
    except Exception as e:
      logging.error(f"ERROR (db.py): Failed to initialize Firestore client: {e}")
      traceback.print_exc()
      FIRESTORE_CLIENT = None
      return False
  return True

# In db.py

# In db.py

def save_trip_to_firestore(user_id: str, itinerary: Itinerary) -> Optional[str]:
  if not FIRESTORE_CLIENT and not initialize_firestore_client(): # Ensure client is initialized
    logging.error("ERROR (db.py): Firestore client not available in save_trip_to_firestore.")
    return None

  try:
    trip_id = str(uuid.uuid4())
    doc_ref = FIRESTORE_CLIENT.collection(TRIPS_COLLECTION).document(trip_id)

    # Create the main Pydantic model, but we'll handle created_at separately for Firestore
    trip_data_for_pydantic = StoredTripDocument(
        trip_id=trip_id,
        user_id=user_id,
        trip_name=itinerary.trip_name or "Untitled Trip",
        start_date=itinerary.start_date,
        end_date=itinerary.end_date,
        itinerary_details=itinerary,
        created_at=None, # Placeholder, will be replaced by Firestore Sentinel
        status="upcoming"
    )

    # Convert Pydantic model to a dictionary first
    data_to_set: Dict[str, Any]
    try:
      # Pydantic V2: mode='python' gets basic Python types where possible,
      # but we need to ensure nested Pydantic models are also dicts.
      # mode='json' would serialize too much (e.g. datetimes to strings before Firestore can handle them).
      # Safest is to dump to dict, then replace.
      data_to_set = trip_data_for_pydantic.model_dump(exclude_none=True)
    except AttributeError: # Fallback for Pydantic V1
      data_to_set = trip_data_for_pydantic.dict(exclude_none=True)

    # Now, explicitly set the Firestore server timestamp sentinel in the dictionary
    data_to_set['created_at'] = firestore.SERVER_TIMESTAMP

    doc_ref.set(data_to_set) # Pass the dictionary with the Sentinel directly to Firestore

    logging.info(f"INFO (db.py): Trip saved to Firestore with ID: {trip_id} for user: {user_id}")
    return trip_id
  except Exception as e:
    logging.error(f"ERROR (db.py): Failed to save trip to Firestore for user {user_id}: {e}")
    traceback.print_exc()
    return None

def get_trips_for_user_from_firestore(user_id: str, status: Optional[str] = "upcoming") -> List[Dict[str, Any]]:
  if not FIRESTORE_CLIENT and not initialize_firestore_client():
    logging.error("ERROR (db.py): Firestore client not available in get_trips_for_user.")
    return []

  try:
    query = FIRESTORE_CLIENT.collection(TRIPS_COLLECTION).where("user_id", "==", user_id)
    if status:
      query = query.where("status", "==", status)
    # Ensure the composite index for this query exists in Firestore:
    # user_id (ASC), status (ASC), start_date (ASC)
    query = query.order_by("start_date", direction=firestore.Query.ASCENDING)

    trips_summary = []
    for doc_snapshot in query.stream():
      trip_data = doc_snapshot.to_dict()
      trips_summary.append({
          "trip_id": trip_data.get("trip_id"),
          "trip_name": trip_data.get("trip_name", "Untitled Trip"), # Add default
          "start_date": trip_data.get("start_date"),
          "end_date": trip_data.get("end_date"),
          "status": trip_data.get("status")
      })
    logging.info(f"INFO (db.py): Retrieved {len(trips_summary)} trips for user: {user_id} status: {status}")
    return trips_summary
  except Exception as e:
    logging.error(f"ERROR (db.py): Failed to get trips from Firestore for user {user_id}: {e}")
    traceback.print_exc()
    return []

def get_trip_details_from_firestore(trip_id: str) -> Optional[Itinerary]:
  if not FIRESTORE_CLIENT and not initialize_firestore_client():
    logging.error("ERROR (db.py): Firestore client not available in get_trip_details.")
    return None

  try:
    doc_ref = FIRESTORE_CLIENT.collection(TRIPS_COLLECTION).document(trip_id)
    doc_snapshot = doc_ref.get()
    if doc_snapshot.exists:
      trip_data_dict = doc_snapshot.to_dict()
      itinerary_details_dict = trip_data_dict.get("itinerary_details")
      if itinerary_details_dict:
        try: # Pydantic V2
          return Itinerary.model_validate(itinerary_details_dict)
        except AttributeError: # Pydantic V1
          return Itinerary(**itinerary_details_dict)
      logging.warning(f"WARNING (db.py): Itinerary details missing for trip ID {trip_id}.")
      return None
    else:
      logging.warning(f"WARNING (db.py): Trip with ID {trip_id} not found in Firestore.")
      return None
  except Exception as e:
    logging.error(f"ERROR (db.py): Failed to get trip details from Firestore for ID {trip_id}: {e}")
    traceback.print_exc()
    return None