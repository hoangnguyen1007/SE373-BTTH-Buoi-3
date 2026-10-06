import os
import json
from typing import List, Optional, Any, Dict
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage, HumanMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from src.domain.models import FlightConstraints


class MockFlightChatModel(BaseChatModel):
    """
    LangChain BaseChatModel returning tool calls for flight booking.
    Enables 100% offline testing without requiring paid API keys.
    """
    constraints: FlightConstraints
    _tools: List[Any] = []

    def bind_tools(self, tools: Any, **kwargs: Any) -> Any:
        self._tools = list(tools)
        return self

    def _generate(self, messages: List[BaseMessage], stop: Optional[List[str]] = None, **kwargs) -> ChatResult:
        # Check latest tool messages to decide next action
        tool_messages = [m for m in messages if isinstance(m, ToolMessage)]

        if not tool_messages:
            # First turn: search flights
            return ChatResult(generations=[
                ChatGeneration(message=AIMessage(
                    content="Searching available flights matching criteria.",
                    tool_calls=[{
                        "name": "search_flights",
                        "args": {
                            "origin": self.constraints.origin,
                            "destination": self.constraints.destination,
                            "date": self.constraints.date,
                        },
                        "id": "call_search_1",
                    }]
                ))
            ])

        last_tool = tool_messages[-1]
        try:
            content = json.loads(last_tool.content) if isinstance(last_tool.content, str) else last_tool.content
        except Exception:
            content = {}

        # After search_flights
        if "flights" in content:
            flights = content.get("flights", [])
            valid_flights = [
                f for f in flights
                if f.get("depart", "") < self.constraints.depart_before and f.get("price", 0) <= self.constraints.max_price
            ]
            if not valid_flights:
                return ChatResult(generations=[
                    ChatGeneration(message=AIMessage(content="No suitable flights found matching constraints."))
                ])

            best = valid_flights[0]["flight"]
            return ChatResult(generations=[
                ChatGeneration(message=AIMessage(
                    content=f"Selected flight {best}. Checking available seats.",
                    tool_calls=[{
                        "name": "check_seat",
                        "args": {"flight_id": best},
                        "id": "call_seat_1",
                    }]
                ))
            ])

        # After check_seat
        if "available_seats" in content:
            seats = content.get("available_seats", [])
            flight_id = content.get("flight", "")
            if not seats:
                return ChatResult(generations=[
                    ChatGeneration(message=AIMessage(content=f"Flight {flight_id} has no available seats."))
                ])

            selected_seat = seats[0]
            return ChatResult(generations=[
                ChatGeneration(message=AIMessage(
                    content=f"Reserving seat {selected_seat} on flight {flight_id}.",
                    tool_calls=[{
                        "name": "book_seat",
                        "args": {"flight_id": flight_id, "seat_number": selected_seat},
                        "id": "call_book_1",
                    }]
                ))
            ])

        # After book_seat
        if content.get("status") == "held":
            code = content.get("booking_code", "")
            return ChatResult(generations=[
                ChatGeneration(message=AIMessage(
                    content=f"Booking code {code} held. Processing payment.",
                    tool_calls=[{
                        "name": "pay",
                        "args": {"booking_code": code, "payment_method": "corp_card"},
                        "id": "call_pay_1",
                    }]
                ))
            ])

        # After pay
        if content.get("status") == "paid":
            code = content.get("booking_code", "")
            return ChatResult(generations=[
                ChatGeneration(message=AIMessage(
                    content=f"Payment completed for booking {code}.",
                    tool_calls=[{
                        "name": "get_booking",
                        "args": {"booking_code": code},
                        "id": "call_verify_1",
                    }]
                ))
            ])

        # Completion turn
        if content.get("status") == "confirmed":
            code = content.get("booking_code", "")
            return ChatResult(generations=[
                ChatGeneration(message=AIMessage(
                    content=f"Booking confirmed successfully! PNR: {code}."
                ))
            ])

        return ChatResult(generations=[
            ChatGeneration(message=AIMessage(content="Task finished."))
        ])

    @property
    def _llm_type(self) -> str:
        return "mock-flight-chat-model"


def get_chat_model(constraints: FlightConstraints) -> BaseChatModel:
    """Return live LLM if API key is present, otherwise return MockFlightChatModel."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key and os.environ.get("RUN_MODE") == "live":
        try:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(model=os.environ.get("SE373_MODEL", "gpt-4o-mini"))
        except ImportError:
            pass

    return MockFlightChatModel(constraints=constraints)
