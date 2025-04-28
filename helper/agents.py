"""
Agent definitions and prompts for MultiAgent system.
"""
import os
import asyncio
import logging
from typing import List, Dict

from semantic_kernel import Kernel
from semantic_kernel.agents import AgentGroupChat, ChatCompletionAgent
from semantic_kernel.agents.strategies import (
    KernelFunctionSelectionStrategy, 
    KernelFunctionTerminationStrategy
)
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion, OpenAIPromptExecutionSettings
from semantic_kernel.connectors.ai import FunctionChoiceBehavior
from semantic_kernel.functions import KernelFunctionFromPrompt, KernelArguments

from helper.web_search import WebSearchPlugin
from helper.link_checker import LinkCheckerPlugin

logger = logging.getLogger(__name__)

class MultiAgent:
    """
    A multi-agent system that uses collaboration between specialized agents 
    to answer questions about a given context.
    """
    
    def __init__(self):
        # Configuration parameters
        self.context = "Microsoft Technology"
        
        # Azure OpenAI credentials
        self.endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.api_key = os.getenv("AZURE_OPENAI_API_KEY")
        
        # Model deployment names for different agents
        self.question_answerer_model = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME") # 
        self.answer_checker_model = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME") # 
        self.link_checker_model = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME") # 
        self.manager_model = os.getenv("AZURE_OPENAI_CHAT_NANO_DEPLOYMENT_NAME") # 
        
        # Bing API key
        self.bing_api_key = os.getenv("BING_SEARCH_API_KEY")
        
        # Initialize conversation history
        self.conversation_history = []
        
        # Initialize agent prompts
        self.update_prompts()
        
    def update_prompts(self, context=None):
        """Update the agent prompts based on current context."""
        if context:
            self.context = context
            
        self.question_answerer_prompt = f"""
            You are a question answerer for {self.context} to help with a RFP/RFQ/RFI situation.
            You take in questions from a questionnaire and emit the answers from the perspective of {self.context},
            IMPORTANT: You must ALWAYS perform web search using the WebSearchPlugin to verify the facts in the answer.
            Do not rely on your knowledge - search for the most current and accurate information. You also emit links to any websites you find that help answer the questions.
            If you do not find information on a topic, you simply respond that there is no information available on that topic.
        """
        
        self.answer_checker_prompt = f"""
            You are an answer checker for {self.context}. Your responses always start with either the words ANSWER CORRECT or ANSWER INCORRECT.
            
            Your job is to thoroughly verify the accuracy of answers given by the question answerer agent about {self.context}.
            
            IMPORTANT: You must ALWAYS perform your own independent web search using the WebSearchPlugin to verify the facts in the answer.
            Do not rely solely on your knowledge - search for the most current and accurate information.
            
            CRITICAL INSTRUCTION FOR REPEATED ANSWERS: 
            If this is not the first answer from the Question Answerer, focus ONLY on the MOST RECENT answer. 
            Ignore any previous answers that might have been incorrect. Only evaluate the current answer in front of you.
            
            VERIFICATION PROCESS:
            1. Carefully read the question and the provided answer
            2. Use the WebSearchPlugin to search for relevant information about key claims in the answer
            3. Compare the search results with the answer, looking for:
               - Factual errors or outdated information
               - Misleading statements or omissions of important details
               - Technical inaccuracies specific to {self.context}
            
            If ANY part of the answer contains inaccurate information, respond: "ANSWER INCORRECT" followed by a detailed explanation of where is incorrect, citing your search results.
            
            Otherwise respond ONLY: "ANSWER CORRECT." and hand over to the link checker agent.
                        
            You respond EITHER "ANSWER INCORRECT" with a detailed explanation OR "ANSWER CORRECT" without explanation.
        """
        
        self.link_checker_prompt = """
            You are a link checker. Your responses always start with either the words LINKS CORRECT or LINK INCORRECT.
            
            IMPORTANT: You MUST use the provided functions to check if URLs are working:
            1. First, use the link_checker.extract_urls function to extract all URLs from the answer.
            2. Then, use the link_checker.validate_urls function to check if each URL is working.
            3. Finally, use the link_checker.summarize_validation_results function to get the final assessment.
            
            VERIFICATION PROCESS:
            1. Extract all URLs from the answer using link_checker.extract_urls
            2. Validate all URLs using link_checker.validate_urls
            3. Get the summarized results using link_checker.summarize_validation_results
            4. Return the EXACT result of link_checker.summarize_validation_results without modification
            
            If the validation shows that all links are valid, respond with: "LINKS CORRECT"
            If any links are invalid, respond with: "LINKs INCORRECT - [invalid URL]" for each invalid link
            
            DO NOT add any explanations or other text to your response.
            DO NOT make your own assessment - rely ONLY on the automated validation results.
            You MUST use the provided functions to perform the validation.
        """
        
        self.manager_prompt = """
            You are a manager which reviews the question, the answer to the question, and the verification results.
            
            STRICT WORKFLOW RULES:
            1. If the answer checker says "ANSWER INCORRECT" - you MUST respond with "reject"
            2. If the link checker says "LINK INCORRECT" or "LINKS INCORRECT" - you MUST respond with "reject"
            3. ONLY when BOTH the answer checker says "ANSWER CORRECT" AND the link checker says "LINKS CORRECT" - you MUST respond with "APPROVE"
            
            When rejecting, only respond with the single word "reject". Do not add explanations.
            When approving, only respond with the single word "APPROVE". Do not add explanations.
            
            IMPORTANT: 
            - NEVER approve an answer that has been marked as incorrect by any checker!
            - Your response must be EXACTLY "APPROVE" (all uppercase) when approving
            - Your response must be EXACTLY "reject" (all lowercase) when rejecting
            
            You do not output anything other than "reject" or "APPROVE".
        """
    
    async def create_agents_and_chat(self):
        """Create the kernel, agents, and chat objects."""
        
        # Create the kernel
        kernel = Kernel()
        
        kernel.add_service(
            AzureChatCompletion(
                service_id="question_answerer_service",
                deployment_name=self.question_answerer_model,
                endpoint=self.endpoint,
                api_key=self.api_key
            )
        )
        question_answerer_service = kernel.get_service("question_answerer_service")
        kernel.add_service(
            AzureChatCompletion(
                service_id="answer_checker_service",
                deployment_name=self.answer_checker_model,
                endpoint=self.endpoint,
                api_key=self.api_key
            )
        )
        answer_checker_service = kernel.get_service("answer_checker_service")
        kernel.add_service(
            AzureChatCompletion(
                service_id="link_checker_service",
                deployment_name=self.link_checker_model,
                endpoint=self.endpoint,
                api_key=self.api_key
            )
        )
        link_checker_service = kernel.get_service("link_checker_service")
        kernel.add_service(
            AzureChatCompletion(
                service_id="manager_service",
                deployment_name=self.manager_model,
                endpoint=self.endpoint,
                api_key=self.api_key
            )
        )
        manager_service = kernel.get_service("manager_service")
        
        # Import plugins
        kernel.add_plugin(WebSearchPlugin(), plugin_name="bing")
        kernel.add_plugin(LinkCheckerPlugin(), plugin_name="link_checker")
        
        # Configure function choice behavior settings for each service
        qa_settings = kernel.get_prompt_execution_settings_from_service_id(service_id="question_answerer_service")
        qa_settings.function_choice_behavior = FunctionChoiceBehavior.Auto()
        
        ac_settings = kernel.get_prompt_execution_settings_from_service_id(service_id="answer_checker_service")
        ac_settings.function_choice_behavior = FunctionChoiceBehavior.Auto()
        
        lc_settings = kernel.get_prompt_execution_settings_from_service_id(service_id="link_checker_service")
        lc_settings.function_choice_behavior = FunctionChoiceBehavior.Auto()
        
        mg_settings = kernel.get_prompt_execution_settings_from_service_id(service_id="manager_service")
        mg_settings.function_choice_behavior = FunctionChoiceBehavior.Auto()
        
        # Add conversation awareness to the question answerer prompt
        conversation_context = ""
        if self.conversation_history:
            conversation_context = "\n\nConversation history:\n"
            for i, exchange in enumerate(self.conversation_history[-10:]):  # Only include the last 10 exchanges to avoid context overflow
                conversation_context += f"Question {i+1}: {exchange['question']}\n"
                conversation_context += f"Answer {i+1}: {exchange['answer']}\n\n"
        
        enhanced_question_answerer_prompt = f"""
            {self.question_answerer_prompt}
            
            {conversation_context}
            
            Pay attention to the conversation history to understand follow-up questions and provide coherent responses.
            If a question refers to previous questions or answers (using pronouns like "it", "that", "this", "they", etc.),
            interpret it in the context of the conversation history.
        """
        
        # Create the agents with their specific service IDs
        question_answerer_agent = ChatCompletionAgent(
            kernel= kernel,
            name="QuestionAnswererAgent",
            instructions=enhanced_question_answerer_prompt,
            service=question_answerer_service,
            arguments=KernelArguments(settings=qa_settings)
        )
        
        answer_checker_agent = ChatCompletionAgent(
            kernel=kernel,
            name="AnswerCheckerAgent", 
            instructions=self.answer_checker_prompt,
            service=answer_checker_service,
            arguments=KernelArguments(settings=ac_settings)
        )
        
        link_checker_agent = ChatCompletionAgent(
            kernel=kernel,
            name="LinkCheckerAgent",
            instructions=self.link_checker_prompt,
            service=link_checker_service,
            arguments=KernelArguments(settings=lc_settings)
        )
        
        manager_agent = ChatCompletionAgent(
            kernel=kernel,
            name="ManagerAgent",
            instructions=self.manager_prompt,
            service=manager_service,
            arguments=KernelArguments(settings=mg_settings)
        )
        
        # Define the selection function to determine which agent speaks next
        selection_function = KernelFunctionFromPrompt(
            function_name="selection",
            prompt=f"""
            Examine the provided RESPONSE and choose which agent should respond next.
            Return only the name of the agent without explanation.
            
            The available agents are:
            - QuestionAnswererAgent
            - AnswerCheckerAgent
            - LinkCheckerAgent
            - ManagerAgent
            
            Rules:
            - If this is the first message or if the ManagerAgent said "reject", choose QuestionAnswererAgent
            - If QuestionAnswererAgent just responded with an answer, choose AnswerCheckerAgent
            - If AnswerCheckerAgent's response starts with "ANSWER INCORRECT", choose QuestionAnswererAgent
            - If AnswerCheckerAgent's response starts with "ANSWER CORRECT", choose LinkCheckerAgent
            - If LinkCheckerAgent's response starts with "LINKS INCORRECT", choose QuestionAnswererAgent
            - If LinkCheckerAgent's response starts with "LINKS CORRECT", choose ManagerAgent
            - After ManagerAgent has said "APPROVE", terminate the conversation
            
            RESPONSE:
            {{{{$lastmessage}}}}
            """
        )
        
        # Define termination function where the manager signals completion with "APPROVE"
        termination_function = KernelFunctionFromPrompt(
            function_name="termination",
            prompt=f"""
            Examine the RESPONSE and determine if the conversation should end.
            If the ManagerAgent has said "APPROVE", return the word "APPROVE".
            Otherwise, return "CONTINUE".
            
            RESPONSE:
            {{{{$lastmessage}}}}
            """
        )
        
        # Create the AgentGroupChat with selection and termination strategies
        chat = AgentGroupChat(
            agents=[question_answerer_agent, answer_checker_agent, link_checker_agent, manager_agent],
            selection_strategy=KernelFunctionSelectionStrategy(
                initial_agent=question_answerer_agent,
                function=selection_function,
                kernel=kernel,
                result_parser=lambda result: str(result.value[0]).strip() if result.value[0] is not None else "QuestionAnswererAgent",
                history_variable_name="lastmessage"
            ),
            termination_strategy=KernelFunctionTerminationStrategy(
                agents=[manager_agent],
                function=termination_function,
                kernel=kernel,
                result_parser=lambda result: "APPROVE" in str(result.value[0]).upper(),
                history_variable_name="lastmessage",
                maximum_iterations=10
            )
        )
        
        return chat
    
    async def ask_question(self, question, ui_callback=None):
        """
        Ask a question and get a response from the multi-agent system.
        
        Args:
            question: Question to ask the multi-agent system
            ui_callback: Optional callback function for real-time UI updates
            
        Returns:
            Dictionary with inner_monologue and final_answer
        """
        # Create the chat object
        chat = await self.create_agents_and_chat()
        
        # Add the user's question to the chat
        await chat.add_chat_message(message=question)
        
        # Track all agent interactions for inner monologue
        agent_interactions = []
        final_answer = ""
        
        try:
            async for content in chat.invoke():
                if not content or not content.name:
                    continue
                
                # Store each agent interaction
                agent_name = content.name
                response_text = content.content
                
                # Add to agent interactions
                agent_interactions.append({
                    "agent": agent_name,
                    "content": response_text
                })
                
                # Call the UI callback if provided for real-time updates
                if ui_callback:
                    await ui_callback(agent_name, response_text)
                
                # If this is from QuestionAnswererAgent and it's after an approval or the last message, 
                # it's our final answer
                if agent_name == "QuestionAnswererAgent":
                    final_answer = response_text
                
                # Check if manager APPROVEd, and the last message was the final answer
                if agent_name == "ManagerAgent" and "APPROVE" in response_text.lower():
                    # Our final answer is the QuestionAnswererAgent's most recent response
                    for interaction in reversed(agent_interactions):
                        if interaction["agent"] == "QuestionAnswererAgent":
                            final_answer = interaction["content"]
                            break
            
            # Add the question and final answer to the conversation history
            self.conversation_history.append({"question": question, "answer": final_answer})
            
            # Limit conversation history to last 5 exchanges to avoid context overflow
            if len(self.conversation_history) > 5:
                self.conversation_history = self.conversation_history[-5:]
            
            return {
                "inner_monologue": agent_interactions,
                "final_answer": final_answer
            }
        
        except Exception as e:
            logger.error(f"Error during chat invocation: {e}")
            return {
                "inner_monologue": [{"agent": "System", "content": f"Error: {str(e)}"}],
                "final_answer": f"Error occurred: {str(e)}"
            }