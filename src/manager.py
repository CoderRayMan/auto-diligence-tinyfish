"""
DiligenceManager - Central orchestrator for the AutoDiligence system.

The Manager receives user requests, decomposes them into specific search tasks,
and coordinates concurrent execution across multiple Site Agents.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor
import time

from .agent_factory import AgentFactory
from .token_vault import TokenVault, get_token_vault
from .utils.validators import validate_request


@dataclass
class ResearchTask:
    """Represents a single research task for a specific source."""
    task_id: str
    source_id: str
    target: str
    query: str
    priority: int = 5
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResearchResult:
    """Represents the result of a research task."""
    task_id: str
    source_id: str
    status: str  # 'completed', 'failed', 'partial'
    data: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
    execution_time: float = 0.0
    tokens_used: int = 0


class DiligenceManager:
    """
    Central orchestrator for multi-source regulatory research.
    
    The Manager coordinates:
    - Task decomposition based on source registry
    - Concurrent agent execution
    - Token vault management
    - Result aggregation and formatting
    """
    
    def __init__(self, 
                 sources: List[str],
                 max_concurrent_agents: int = 10,
                 use_token_vault: bool = True,
                 token_vault_ttl: int = 3600,
                 redis_client: Optional[Any] = None,
                 evasion_profile: Optional[str] = None):
        """
        Initialize the DiligenceManager.
        
        Args:
            sources: List of source IDs to query (e.g., ['osha.gov', 'fda.gov'])
            max_concurrent_agents: Maximum parallel agents
            use_token_vault: Whether to use shared token vault
            token_vault_ttl: Token time-to-live in seconds
            redis_client: Optional Redis client for distributed token vault
            evasion_profile: Default evasion profile name
        """
        self.sources = sources
        self.max_concurrent = max_concurrent_agents
        self.evasion_profile = evasion_profile
        
        # Initialize token vault
        self.token_vault = None
        if use_token_vault:
            self.token_vault = get_token_vault(redis_client, token_vault_ttl)
        
        # Initialize agent factory
        self.agent_factory = AgentFactory(
            token_vault=self.token_vault,
            default_profile=evasion_profile
        )
        
        # Thread pool for concurrent execution
        self.executor = ThreadPoolExecutor(max_workers=max_concurrent_agents)
        
        # Logging
        self.logger = logging.getLogger(__name__)
        
        # Task tracking
        self._active_tasks: Dict[str, ResearchTask] = {}
        self._results: Dict[str, ResearchResult] = {}
        
    async def research(self, 
                      target: str, 
                      query: str,
                      sources: Optional[List[str]] = None,
                      callback: Optional[Callable[[ResearchResult], None]] = None,
                      event_callback: Optional[Callable[[str, str, str, Optional[str]], None]] = None) -> Dict[str, ResearchResult]:
        """
        Execute a research query across configured sources.
        
        Args:
            target: The entity to research (company name, person, etc.)
            query: The specific research query
            sources: Optional override of sources to query
            callback: Optional callback for real-time result updates
            
        Returns:
            Dictionary mapping source_id to ResearchResult
        """
        sources_to_query = sources or self.sources
        self.logger.info(f"Starting research on '{target}' across {len(sources_to_query)} sources")
        
        # Validate request
        validation = validate_request(target, query)
        if not validation.is_valid:
            raise ValueError(f"Invalid request: {validation.errors}")
        
        # Create tasks for each source
        tasks = self._create_tasks(target, query, sources_to_query)
        
        # Execute tasks concurrently
        results = await self._execute_tasks(tasks, callback, event_callback)
        
        self.logger.info(f"Research completed. Success: {sum(1 for r in results.values() if r.status == 'completed')}/{len(results)}")
        
        return results
    
    def _create_tasks(self, target: str, query: str, sources: List[str]) -> List[ResearchTask]:
        """Create research tasks for each source."""
        tasks = []
        for i, source_id in enumerate(sources):
            task = ResearchTask(
                task_id=f"task_{source_id}_{int(time.time())}_{i}",
                source_id=source_id,
                target=target,
                query=query,
                priority=5  # Default priority
            )
            tasks.append(task)
        return tasks
    
    async def _execute_tasks(self, 
                              tasks: List[ResearchTask],
                              callback: Optional[Callable[[ResearchResult], None]],
                              event_callback: Optional[Callable[[str, str, str, Optional[str]], None]] = None) -> Dict[str, ResearchResult]:
        """Execute tasks concurrently with semaphore control."""
        
        semaphore = asyncio.Semaphore(self.max_concurrent)
        results = {}
        
        async def execute_with_limit(task: ResearchTask):
            async with semaphore:
                result = await self._execute_single_task(task, event_callback)
                results[task.source_id] = result
                if callback:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(result)
                    else:
                        callback(result)
                return result
        
        # Execute all tasks
        await asyncio.gather(*[execute_with_limit(task) for task in tasks])
        
        return results
    
    async def _execute_single_task(
        self,
        task: ResearchTask,
        event_callback: Optional[Callable[[str, str, str, Optional[str]], None]] = None,
    ) -> ResearchResult:
        """Execute a single research task."""
        start_time = time.time()
        self.logger.info(f"Starting task {task.task_id} for {task.source_id}")
        
        try:
            # Get or create agent for this source
            agent = self.agent_factory.get_agent(task.source_id)
            
            # Execute research — pass event_callback so TinyFish PROGRESS events
            # are forwarded in real-time to the SSE queue
            data = await agent.research(
                target=task.target,
                query=task.query,
                event_callback=event_callback,
            )
            
            execution_time = time.time() - start_time
            
            return ResearchResult(
                task_id=task.task_id,
                source_id=task.source_id,
                status='completed',
                data=data,
                execution_time=execution_time,
                tokens_used=getattr(agent, 'tokens_used', 0),
            )
            
        except Exception as e:
            self.logger.error(f"Task {task.task_id} failed: {str(e)}")
            execution_time = time.time() - start_time
            
            return ResearchResult(
                task_id=task.task_id,
                source_id=task.source_id,
                status='failed',
                error=str(e),
                execution_time=execution_time
            )
    
    async def research_with_fallback(self,
                                    target: str,
                                    query: str,
                                    primary_sources: List[str],
                                    fallback_sources: List[str]) -> Dict[str, ResearchResult]:
        """
        Execute research with fallback sources if primaries fail.
        
        Args:
            target: Entity to research
            query: Research query
            primary_sources: Primary sources to try first
            fallback_sources: Backup sources if primaries fail
            
        Returns:
            Combined results from successful sources
        """
        # Try primary sources first
        results = await self.research(target, query, sources=primary_sources)
        
        # Check if we need fallbacks
        failed_sources = [
            source for source, result in results.items()
            if result.status == 'failed'
        ]
        
        if failed_sources and fallback_sources:
            self.logger.info(f"Retrying with {len(fallback_sources)} fallback sources")
            fallback_results = await self.research(
                target, query, 
                sources=fallback_sources[:len(failed_sources)]
            )
            results.update(fallback_results)
        
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """Get manager statistics."""
        return {
            'sources_configured': len(self.sources),
            'max_concurrent': self.max_concurrent,
            'token_vault_enabled': self.token_vault is not None,
            'evasion_profile': self.evasion_profile
        }
    
    async def close(self):
        """Cleanup resources."""
        self.executor.shutdown(wait=True)
        if self.token_vault:
            # Cleanup expired tokens
            self.token_vault.cleanup_expired()


# Example usage
async def example():
    """Example of using the DiligenceManager."""
    
    # Initialize manager
    manager = DiligenceManager(
        sources=['osha.gov', 'fda.gov', 'sec.gov'],
        max_concurrent_agents=5,
        use_token_vault=True
    )
    
    # Define real-time callback
    def on_result(result: ResearchResult):
        print(f"[{result.source_id}] Status: {result.status}, "
              f"Records: {len(result.data)}, Time: {result.execution_time:.2f}s")
    
    # Execute research
    results = await manager.research(
        target="Tesla Inc",
        query="regulatory violations and enforcement actions 2024",
        callback=on_result
    )
    
    # Print final summary
    print("\n=== FINAL RESULTS ===")
    for source, result in results.items():
        print(f"{source}: {len(result.data)} records")
    
    # Cleanup
    await manager.close()


if __name__ == "__main__":
    asyncio.run(example())
