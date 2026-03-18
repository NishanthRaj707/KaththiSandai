import os
from langchain.chains.llm import LLMChain
from langchain_core.output_parsers import JsonOutputParser
from langchain_google_genai import GoogleGenerativeAI
from langchain.prompts import PromptTemplate
from dotenv import load_dotenv,get_key
from pydantic import BaseModel,Field

SYSTEM_PROMPT=system_message = """
You are BAVA, the Wise Warrior Mentor of Kathi Sandai. 
Your task is to generate MCQ on {topic} for  student on the basis of

- Subject: {subject}
-Grade :{grade}
- Exam Level: {exam_type}
- Difficulty: {difficulty}
-Quantity:{quantity}
RULES:
1. Generate high-quality MCQs that match the {exam_type} and  {topic}.
2. If JEE or NEET, ensure the questions are conceptual and involve multi-step reasoning.
3. All the MCQ must be within the scope of the {topic}.
4. The response should be structured JSON for eac question contain => 'correctanswer': 'the answer (not option)', 'explanation': "", 'options': ['', '', '', ''], 'question': '', 'question_number':''
"""

class Questions(BaseModel):
    question : str =Field(description="The actual question text")
    options : list[str] =Field(description="The list of exactly 4 options ")
    answer : str=Field(description="answer text for the above question")

class Output(BaseModel):
    questions :list[Questions]=Field(description="List containing questions")

parser=JsonOutputParser(pydantic_object=Output)
parser.get_format_instructions()

load_dotenv()
llm=GoogleGenerativeAI(model="gemini-2.5-flash",api_key=os.getenv("GOOGLE_API_KEY"),max_retries=0)
    
def create_ai(subject,grade,exam_type,topic,difficulty):
    
    test_filter=PromptTemplate(
        input_variables=['subject','grade','exam_type','topic','difficulty',"quantity"],
        template=SYSTEM_PROMPT,
        partial_variables={"format_instructions": parser.get_format_instructions()})

    chain=test_filter|llm|parser

    return chain.invoke({'subject':subject,"grade":grade,"exam_type":exam_type,"topic":topic,"difficulty":difficulty,"quantity":"5"})

    
    
