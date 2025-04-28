"""
Link checker plugin for the MultiAgent system.
"""
import re
import logging
import asyncio
import aiohttp
import urllib.parse
from typing import Dict, List, Tuple, Annotated
from semantic_kernel.functions import kernel_function

logger = logging.getLogger(__name__)

class LinkCheckerPlugin:
    """A plugin for checking links in text."""
    
    @kernel_function(description="Extract URLs from text.")
    async def extract_urls(
        self,
        text: Annotated[str, "The text to extract URLs from."]
    ) -> Annotated[str, "List of URLs extracted from the text."]:
        """Extract URLs from a piece of text."""
        # Regular expression to find URLs
        url_pattern = r'https?://[^\s\)\]\"\'\>]+'
        urls = re.findall(url_pattern, text)
        
        if not urls:
            return "No URLs found in the text."
        
        return "\n".join(urls)
    
    @kernel_function(description="Validate URLs to check if they are functioning correctly.")
    async def validate_urls(
        self,
        urls: Annotated[str, "A list of URLs to check, one per line."],
        timeout: Annotated[int, "Timeout in seconds for each request."] = 10,
        max_redirects: Annotated[int, "Maximum number of redirects to follow."] = 5
    ) -> Annotated[str, "Results of URL validation."]:
        """
        Validate a list of URLs to check if they are working.
        
        Args:
            urls: Newline-separated list of URLs to validate
            timeout: Timeout in seconds for each request
            max_redirects: Maximum number of redirects to follow
            
        Returns:
            String with validation results for each URL
        """
        if not urls or urls == "No URLs found in the text.":
            return "No URLs to validate."
            
        url_list = urls.strip().split('\n')
        url_list = [url for url in url_list if url.strip()]
        
        if not url_list:
            return "No valid URLs to check."
        
        results = []
        valid_status_codes = range(200, 400)  # 2xx and 3xx status codes are considered valid
        
        # Use aiohttp for efficient concurrent HTTP requests
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=timeout),
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) LinkValidator/1.0"}
        ) as session:
            tasks = []
            
            for url in url_list:
                # Clean up URL
                url = url.strip()
                if not url:
                    continue
                    
                # Parse URL to handle malformed URLs
                try:
                    parsed_url = urllib.parse.urlparse(url)
                    if not parsed_url.scheme or not parsed_url.netloc:
                        results.append(f"INVALID: {url} - Malformed URL")
                        continue
                except Exception as e:
                    results.append(f"INVALID: {url} - {str(e)}")
                    continue
                
                # Add task for async checking
                tasks.append(self._check_url(session, url, max_redirects))
            
            # Wait for all checks to complete
            check_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for url, result in zip(url_list, check_results):
                if isinstance(result, Exception):
                    results.append(f"INVALID: {url} - {str(result)}")
                elif result['success']:
                    results.append(f"VALID: {url} - Status {result['status_code']}")
                else:
                    results.append(f"INVALID: {url} - {result['message']}")
        
        return "\n".join(results)
    
    async def _check_url(
        self, 
        session: aiohttp.ClientSession, 
        url: str, 
        max_redirects: int
    ) -> Dict:
        """
        Check a URL to see if it's valid and working.
        
        Args:
            session: aiohttp client session
            url: URL to check
            max_redirects: Maximum number of redirects to follow
            
        Returns:
            Dictionary with check results
        """
        try:
            # First try a HEAD request as it's more efficient
            try:
                async with session.head(
                    url, 
                    allow_redirects=True,
                    max_redirects=max_redirects,
                    ssl=False  # Don't validate SSL certificates to handle more URLs
                ) as response:
                    status = response.status
                    final_url = str(response.url)
                    
                    # If it's a success or redirect, return success
                    if 200 <= status < 400:
                        return {
                            'success': True, 
                            'status_code': status,
                            'final_url': final_url
                        }
                    
                    # Some servers don't support HEAD, fall back to GET
                    if status in (404, 405, 403):
                        raise aiohttp.ClientResponseError(
                            response.request_info, 
                            response.history,
                            status=status,
                            message=f"HEAD request failed with status {status}, trying GET"
                        )
                    
                    return {
                        'success': False,
                        'status_code': status,
                        'message': f"HTTP Error: {status}"
                    }
                    
            except (aiohttp.ClientResponseError, aiohttp.ClientError):
                # Fall back to GET request if HEAD fails
                async with session.get(
                    url,
                    allow_redirects=True,
                    max_redirects=max_redirects,
                    ssl=False  # Don't validate SSL certificates
                ) as response:
                    status = response.status
                    final_url = str(response.url)
                    
                    # Check for common error page indicators in the content
                    if 200 <= status < 400:
                        # For 200 OK responses, check if it's actually an error page (soft 404)
                        content_type = response.headers.get('Content-Type', '')
                        if 'text/html' in content_type.lower():
                            # Read the content to check for error patterns
                            content = await response.text(encoding='utf-8', errors='ignore')
                            
                            # General error patterns for detecting soft 404s
                            error_patterns = [
                                r'404 - Page not found',
                                r'<title>[^<]*(?:404|not found|error|page does not exist)[^<]*</title>',
                                r'<h1>[^<]*(?:404|not found|error|page does not exist)[^<]*</h1>',
                                r'<h2[^>]*>[^<]*(?:404|not found|error|page does not exist)[^<]*</h2>',
                                r'Sorry, the page you requested cannot be found',
                                r'The page you\'re looking for isn\'t available',
                                r'The resource you are looking for has been removed',
                                r'404 Not Found',
                                r'Page Not Found',
                                r'The page cannot be found',
                                r'This page does not exist',
                                r'We can\'t find the page you\'re looking for'
                            ]
                            
                            # Check general error patterns
                            for pattern in error_patterns:
                                if re.search(pattern, content, re.IGNORECASE):
                                    return {
                                        'success': False,
                                        'status_code': 404,  # Treat as a 404
                                        'message': f"Soft 404 detected: Page appears to be an error page despite 200 status"
                                    }
                    
                    if 200 <= status < 400:
                        return {
                            'success': True,
                            'status_code': status,
                            'final_url': final_url
                        }
                    else:
                        return {
                            'success': False,
                            'status_code': status,
                            'message': f"HTTP Error: {status}"
                        }
                        
        except aiohttp.ClientConnectorError as e:
            return {
                'success': False,
                'message': f"Connection error: {str(e)}"
            }
        except aiohttp.ClientError as e:
            return {
                'success': False,
                'message': f"Request error: {str(e)}"
            }
        except asyncio.TimeoutError:
            return {
                'success': False,
                'message': "Request timed out"
            }
        except Exception as e:
            logger.error(f"Error checking URL {url}: {str(e)}")
            return {
                'success': False,
                'message': f"Unexpected error: {str(e)}"
            }
            
    @kernel_function(description="Summarize link validation results.")
    def summarize_validation_results(
        self,
        validation_results: Annotated[str, "Validation results from validate_urls function."]
    ) -> Annotated[str, "Summary of link validation results."]:
        """
        Summarize the validation results into a simple format.
        
        Args:
            validation_results: String with validation results
            
        Returns:
            String with summarized results
        """
        if not validation_results or validation_results in ("No URLs to validate.", "No valid URLs to check."):
            return "LINKS CORRECT"  # No links is not an error
            
        lines = validation_results.strip().split('\n')
        invalid_links = []
        
        for line in lines:
            if line.startswith("INVALID:"):
                # Extract just the URL from the validation result
                parts = line.split(" - ", 1)
                if len(parts) > 0:
                    url = parts[0].replace("INVALID:", "").strip()
                    invalid_links.append(url)
        
        if invalid_links:
            return "\n".join([f"LINK INCORRECT - {link}" for link in invalid_links])
        else:
            return "LINKS CORRECT"