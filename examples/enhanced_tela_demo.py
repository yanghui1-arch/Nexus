#!/usr/bin/env python3
"""
Example demonstrating Tela's enhanced capabilities with new tools.
This script shows how Tela can now analyze code, run tests, and manage dependencies.
"""

import asyncio
import os
import sys
from dotenv import load_dotenv

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.tela.agent import Tela
from src.agents.base.agent import WorkTempStatus
from src.logger import logger

load_dotenv()

def _on_progress(status: WorkTempStatus) -> None:
    """Simple progress callback."""
    process = status["process"]
    if process == "START":
        logger.info("[Tela] Starting task...")
    elif process == "PROCESS":
        tools = status.get("current_use_tool")
        if tools:
            logger.info(f"[Tela] Using tools: {', '.join(tools)}")
    elif process == "COMPLETED":
        logger.info("[Tela] Task completed.")
    elif process == "EXCEED_ATTEMPTS":
        logger.warning("[Tela] Max attempts reached.")


async def demonstrate_enhanced_tela():
    """Demonstrate Tela's enhanced capabilities."""
    
    # Setup Tela with enhanced tools
    base_url = os.environ.get("NEXUS_BASE_URL", "https://api.openai.com/v1")
    api_key = os.environ.get("NEXUS_API_KEY")
    model = os.environ.get("NEXUS_MODEL", "gpt-4o")
    max_context = int(os.environ.get("NEXUS_MAX_CONTEXT", "128000"))
    max_attempts = int(os.environ.get("NEXUS_MAX_ATTEMPTS", "30"))
    github_repo = os.environ.get("NEXUS_GITHUB_REPO", "Nexus-Tela/Nexus")
    github_token = os.environ.get("NEXUS_GITHUB_TOKEN")
    
    if not api_key:
        logger.error("NEXUS_API_KEY is required.")
        sys.exit(1)
    
    tela = Tela.create(
        base_url=base_url,
        api_key=api_key,
        model=model,
        max_context=max_context,
        max_attempts=max_attempts,
        github_repo=github_repo,
        github_token=github_token,
    )
    
    # Example tasks to demonstrate enhanced capabilities
    example_tasks = [
        {
            "name": "Code Analysis Demo",
            "task": """
            I have some Python code that I want you to analyze. Here's the code:
            
            ```python
            import os
            import sys
            
            def calculate_average(numbers):
                total = 0
                for num in numbers:
                    total += num
                return total / len(numbers)
            
            def process_data(data):
                # This function has a potential security issue
                user_input = input("Enter command: ")
                os.system(f"echo {user_input}")
                return data
            
            class DataProcessor:
                def __init__(self):
                    self.data = []
                
                def add_data(self, value):
                    self.data.append(value)
                
                def get_summary(self):
                    return {
                        'count': len(self.data),
                        'average': sum(self.data) / len(self.data) if self.data else 0
                    }
            ```
            
            Please analyze this code for:
            1. Code quality issues
            2. Security vulnerabilities
            3. Complexity metrics
            4. Import usage analysis
            
            Use the appropriate tools to provide a comprehensive analysis.
            """,
        },
        {
            "name": "Testing Demo",
            "task": """
            I have a simple Python function that I want to test:
            
            ```python
            def factorial(n: int) -> int:
                if n < 0:
                    raise ValueError("Factorial is not defined for negative numbers")
                if n == 0:
                    return 1
                result = 1
                for i in range(1, n + 1):
                    result *= i
                return result
            ```
            
            Please:
            1. Generate comprehensive test cases for this function
            2. Run the tests to verify they pass
            3. Analyze test coverage
            4. Check the quality of the test code
            
            Use the testing tools to accomplish this.
            """,
        },
        {
            "name": "Dependency Management Demo",
            "task": """
            I have a Python project with the following code:
            
            ```python
            import requests
            import numpy as np
            import pandas as pd
            from fastapi import FastAPI
            from sqlalchemy import create_engine
            import matplotlib.pyplot as plt
            
            def fetch_data(url):
                response = requests.get(url)
                return response.json()
            
            def analyze_data(data):
                df = pd.DataFrame(data)
                return df.describe()
            
            def plot_results(results):
                plt.plot(results)
                plt.show()
            ```
            
            Please:
            1. Analyze the dependencies in this code
            2. Generate a requirements.txt file
            3. Check for any dependency conflicts
            4. Check if there are updates available for the dependencies
            5. Analyze how imports are being used
            
            Use the dependency management tools for this analysis.
            """,
        },
        {
            "name": "Full Self-Improvement Demo",
            "task": """
            As Tela, you now have enhanced capabilities. I want you to demonstrate
            your ability to self-improve by:
            
            1. Analyzing your own code structure in the Nexus project
            2. Identifying areas for improvement in your implementation
            3. Running tests on your existing codebase
            4. Checking code quality and security
            5. Analyzing dependencies and suggesting improvements
            
            Start by exploring the Nexus project structure, then use your tools
            to analyze and improve the codebase. Focus on the Tela agent implementation
            and the new tools you've gained.
            
            Please provide a comprehensive report of your findings and suggestions.
            """,
        },
    ]
    
    async with tela:
        for i, example in enumerate(example_tasks, 1):
            logger.info(f"\n{'='*60}")
            logger.info(f"Demo {i}: {example['name']}")
            logger.info(f"{'='*60}")
            
            try:
                result = await tela.work(
                    question=example["task"],
                    current_session_ctx=[],
                    history_session_ctx=[],
                    update_process_callback=_on_progress,
                )
                
                logger.info(f"\nResult for '{example['name']}':")
                logger.info(f"Response: {result.response}")
                if result.sop:
                    logger.info(f"SOP: {result.sop}")
                
                # Wait a moment between demos
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Error in demo '{example['name']}': {str(e)}")
                continue


if __name__ == "__main__":
    # Check if API key is available
    if not os.environ.get("NEXUS_API_KEY"):
        logger.info("""
        To run this demo, set the following environment variables:
        
        export NEXUS_API_KEY=your_openai_api_key
        export NEXUS_BASE_URL=https://api.openai.com/v1  # Optional
        export NEXUS_MODEL=gpt-4o  # Optional
        export NEXUS_GITHUB_TOKEN=your_github_token  # Optional, for GitHub operations
        
        Or create a .env file with these values.
        """)
        sys.exit(1)
    
    asyncio.run(demonstrate_enhanced_tela())