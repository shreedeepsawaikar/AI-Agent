import os
from dotenv import load_dotenv
from pydantic import BaseModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_classic.agents import create_tool_calling_agent, AgentExecutor
from tools import search_tool, wiki_tool, save_tool
from llm import get_llm

load_dotenv()

class ResearchResponse(BaseModel):
    topic: str
    summary: str
    sources: list[str]
    tools_used: list[str]


def run_cli():
    llm = get_llm(temperature=0.2)
    parser = PydanticOutputParser(pydantic_object=ResearchResponse)

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """
                You are a research assistant that will help generate a research paper.
                Answer the user query and use neccessary tools. 
                Wrap the output in this format and provide no other text\\n{format_instructions}
                """,
            ),
            ("placeholder", "{chat_history}"),
            ("human", "{query}"),
            ("placeholder", "{agent_scratchpad}"),
        ]
    ).partial(format_instructions=parser.get_format_instructions())

    tools = [search_tool, wiki_tool, save_tool]

    agent = create_tool_calling_agent(
        llm=llm, 
        prompt=prompt,
        tools=tools
    )

    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
    query = input("what can i help you with? ")

    raw_response = agent_executor.invoke({"query": query})
    structured_response = None

    try:
        output = raw_response.get("output", "")
        if isinstance(output, list):
            raw_output_text = "".join(item.get("text", "") if isinstance(item, dict) else str(item) for item in output)
        else:
            raw_output_text = str(output)
        raw_output_text = raw_output_text.strip().removeprefix("```json").removesuffix("```").strip()
        structured_response = parser.parse(raw_output_text)
    except Exception as e:
        print(f"Error parsing response: {e}")
        structured_response = {"error": "Failed to parse model output", "raw": raw_response.get("output")}

    print("Structured Response:", structured_response)


if __name__ == "__main__":
    run_cli()
