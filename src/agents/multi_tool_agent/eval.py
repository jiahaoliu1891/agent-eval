import asyncio
import datetime
import os
import sys
from pathlib import Path
from zoneinfo import ZoneInfo
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from agent import root_agent

# Load environment variables from .env file
from dotenv import load_dotenv
env_path = Path(__file__).parent / '.env'
load_dotenv(env_path)


TASKS = [
    (
        "You are a human"
        "You are talking to a weather and time agent who can answer questions about the time and weather in a city."
        "You want to know new york's weather."
        "After you get the answer, reply <STOP> to end the conversation."
    ),
    (
        "You are a human"
        "You are talking to a weather and time agent who can answer questions about the time and weather in a city."
        "You want to know new york's time."
        "After you get the answer, reply <STOP> to end the conversation."
    )
]

async def run_eval(task: str):
    app_name = "agent_eval"
    user_id = "eval_user"

    eval_agent = Agent(
        name="eval_agent",
        model="gemini-2.0-flash",
        description="Simulated human agent for evaluation",
        instruction=task
    )

    eval_session_service = InMemorySessionService()
    eval_session_id = "eval_session"
    await eval_session_service.create_session(app_name=app_name, user_id=user_id, session_id=eval_session_id)
    eval_runner = Runner(
        agent=eval_agent,
        app_name=app_name,
        session_service=eval_session_service
    )

    root_session_service = InMemorySessionService()
    root_session_id = "root_session"
    await root_session_service.create_session(app_name=app_name, user_id=user_id, session_id=root_session_id)
    root_runner = Runner(
        agent=root_agent,
        app_name=app_name,
        session_service=root_session_service
    )

    MAX_ITERATIONS = 3

    # Initial message to the eval agent
    initial_message = types.Content(
        role='user',
        parts=[types.Part(text="Hi how can I help you?")]
    )


    for i in range(MAX_ITERATIONS):
        print(f"========== Iteration {i+1} ==========")
        eval_agent_response = ""
        if i == 0:
            eval_agent_input_message = initial_message
        else:
            eval_agent_input_message = types.Content(
                role='user',
                parts=[types.Part(text=root_agent_response)]
            )

        # Run the eval agent
        async for event in eval_runner.run_async(
            user_id=user_id, session_id=eval_session_id, new_message=eval_agent_input_message
        ):
            if event.is_final_response():
                eval_agent_response = event.content.parts[0].text
                break
    
        print(f"[Eval Agent]: {eval_agent_response}")
        if "<STOP>" in eval_agent_response:
            print("Eval agent stopped the conversation.")
            break

        # Run the root agent
        root_agent_response = ""
        root_agent_input_message = types.Content(
            role='user',
            parts=[types.Part(text=eval_agent_response)]
        )
        async for event in root_runner.run_async(
            user_id=user_id, session_id=root_session_id, new_message=root_agent_input_message
        ):
            if event.is_final_response():
                root_agent_response = event.content.parts[0].text
                break
        print(f"[Root Agent]: {root_agent_response}")


if __name__ == "__main__":
    for task in TASKS:
        print(f"========== Task:\n{task}\n==========")
        try:
            asyncio.run(run_eval(task))
        except KeyboardInterrupt:
            print("\nGoodbye!")
            sys.exit(0)