#!/usr/bin/env python
import sys
import warnings
import os
from dotenv import load_dotenv

load_dotenv()
# Ensure our parent directories are in sys.path
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
parent_of_parent_dir = os.path.abspath(os.path.join(parent_dir, ".."))
if parent_of_parent_dir not in sys.path:
    sys.path.insert(0, parent_of_parent_dir)


from backend.agent.convo_newsletter_crew.newsletter_crew import ConvoNewsletterCrew

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

# This main file is intended to be a way for you to run your
# crew locally, so refrain from adding unnecessary logic into this file.
# Replace with inputs you want to test with, it will automatically
# interpolate any tasks and agents information


def run():
    """
    Run the crew.
    """
    inputs = {
        "brain_dump": """
            I would like to write a newsletter around "why is it feels so hard to get a new AI software job or land AI clients". 
            It really comes down to a few idea. They are competing the same way everyone else is by updating their linkedin bio and sending out 
            hundreds of resumes to the same 100 companies that are receiving thousands of applicants which makes them a needle in the hay stack. 
            They aren't opening themselves up to luck by posting their work on YouTube and LinkedIn. Software is one of the only jobs where you can 
            actively demo what you're capabale of in a very public settings. Take advantage of that.
            """
    }

    try:
        ConvoNewsletterCrew().crew().kickoff(inputs=inputs)
    except Exception as e:
        raise Exception(f"An error occurred while running the crew: {e}")


def train():
    """
    Train the crew for a given number of iterations.
    """
    inputs = {"topic": "AI LLMs"}
    try:
        ConvoNewsletterCrew().crew().train(
            n_iterations=int(sys.argv[1]), filename=sys.argv[2], inputs=inputs
        )

    except Exception as e:
        raise Exception(f"An error occurred while training the crew: {e}")


def replay():
    """
    Replay the crew execution from a specific task.
    """
    try:
        ConvoNewsletterCrew().crew().replay(task_id=sys.argv[1])

    except Exception as e:
        raise Exception(f"An error occurred while replaying the crew: {e}")


def test():
    """
    Test the crew execution and returns the results.
    """
    inputs = {"topic": "AI LLMs"}
    try:
        ConvoNewsletterCrew().crew().test(
            n_iterations=int(sys.argv[1]), openai_model_name=sys.argv[2], inputs=inputs
        )

    except Exception as e:
        raise Exception(f"An error occurred while testing the crew: {e}")


if __name__ == "__main__":
    run()
