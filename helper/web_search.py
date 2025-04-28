"""
Web search plugin for the MultiAgent system.
"""
import os
import logging
import aiohttp
import streamlit as st
from typing import Annotated
from semantic_kernel.functions import kernel_function

class WebSearchPlugin:
    """A plugin for searching the web using Bing."""
    
    @kernel_function(description="Search Bing for relevant web information.")
    async def search_web(
        self,
        query: Annotated[str, "The search query in concise terms that works efficiently in Bing Search."],
        up_to_date: Annotated[bool, "Whether up-to-date information is needed."] = False,
        count_per_context: Annotated[int, "Number of results to fetch per context."] = 10
    ) -> Annotated[str, "Search results from the web."]:
        bing_api_key = os.getenv("BING_SEARCH_API_KEY")
        has_bing_api_key = bing_api_key is not None and bing_api_key != ''
        
        if not has_bing_api_key:
            return "Web search is currently unavailable because no Bing Search API key was provided."
        
        bing_api_endpoint = os.getenv("BING_SEARCH_API_ENDPOINT", "https://api.bing.microsoft.com/v7.0/search")
        
        try:
            # URL mapping for different Microsoft documentation contexts
            url_mapping = {
                "Azure AI": "https://learn.microsoft.com/en-us/azure",
                "Fabric": "https://learn.microsoft.com/en-us/fabric/",
                "Copilot Studio": "https://learn.microsoft.com/en-us/microsoft-copilot-studio/",
                "M365 Copilot": "https://learn.microsoft.com/en-us/copilot/microsoft-365/"
            }
            
            # Get the selected contexts from session state, default to ["Azure AI"] if not set
            selected_contexts = st.session_state.get("selected_contexts", ["Azure AI"])
            
            # Use the selected context URLs
            restricted_urls = [url_mapping[ctx] for ctx in selected_contexts if ctx in url_mapping]
                
            if restricted_urls:
                concatenated_url_string = " OR ".join(
                    f"site:{url.replace('https://','').replace('http://','')}" for url in restricted_urls
                )
                query = f"{query} {concatenated_url_string}"
            else: # If no valid contexts are selected, use the original query
                query = query
        except Exception as ex:
            logging.error(f"Error querying ProductUrl container: {ex}")

        headers = {"Ocp-Apim-Subscription-Key": bing_api_key}
        # Calculate count based on number of selected contexts and count_per_context parameter
        context_count = len(selected_contexts) if selected_contexts else 1
        search_count = context_count * count_per_context
        params = {"q": query, "count": search_count}
        
        if up_to_date:
            params.update({"sortby": "Date"})
            
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(bing_api_endpoint, headers=headers, params=params) as response:
                    response.raise_for_status()
                    search_results = await response.json()
                    results = []
                    
                    if search_results and "webPages" in search_results and "value" in search_results["webPages"]:
                        for v in search_results["webPages"]["value"]:
                            result = {
                                "source_title": v["name"],
                                "content": v["snippet"],
                                "source_url": v["url"]
                            }
                            results.append(result)
                            
                    formatted_result = "\n".join([
                        f'{i}. content: {item["content"]}, source_title: {item["source_title"]}, source_url: {item["source_url"]}' 
                        for i, item in enumerate(results, 1)
                    ])
                    
                    return formatted_result
        except Exception as ex:
            return f"Error during web search: {str(ex)}"