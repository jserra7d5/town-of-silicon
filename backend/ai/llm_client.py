"""LLM client for oss-20b with 64K context support via llama.cpp."""
import asyncio
import json
from typing import Optional, TypeVar, Type
from loguru import logger
from pydantic import BaseModel

try:
    from llama_cpp import Llama
    LLAMA_CPP_AVAILABLE = True
except ImportError:
    LLAMA_CPP_AVAILABLE = False
    logger.warning("llama-cpp-python not installed. Install with: pip install llama-cpp-python")

from ..config.settings import settings

T = TypeVar('T', bound=BaseModel)


class LLMClient:
    """
    LLM client optimized for M4 Pro with 64K context.

    Uses llama.cpp with Metal acceleration for maximum performance
    on Apple Silicon.
    """

    def __init__(self):
        self.model: Optional[Llama] = None
        self._loaded = False

    def load_model(self) -> None:
        """Load oss-20b model with 64K context support."""
        if not LLAMA_CPP_AVAILABLE:
            raise RuntimeError("llama-cpp-python not installed")

        if self._loaded:
            logger.info("Model already loaded")
            return

        logger.info(f"Loading model from {settings.llm_model_path}")
        logger.info(f"Context size: {settings.llm_context_size} tokens (64K!)")

        self.model = Llama(
            model_path=settings.llm_model_path,

            # 64K context window!
            n_ctx=settings.llm_context_size,

            # M4 Pro optimizations
            n_gpu_layers=settings.llm_n_gpu_layers,  # All layers on Metal GPU
            n_threads=settings.llm_n_threads,  # Use P-cores
            n_batch=settings.llm_n_batch,

            # Memory optimization
            use_mlock=settings.llm_use_mlock,  # Lock in RAM
            use_mmap=True,  # Memory-map model file

            # Metal acceleration for M4 Pro
            offload_kqv=True,  # Offload KV cache to GPU

            # Logging
            verbose=settings.debug,
        )

        self._loaded = True
        logger.success("Model loaded successfully with 64K context!")

    async def generate(
        self,
        prompt: str,
        max_tokens: int = 200,
        temperature: float = 0.7,
        stop: Optional[list[str]] = None,
    ) -> str:
        """
        Generate text completion.

        Args:
            prompt: Input prompt (can be up to ~60K tokens!)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            stop: Stop sequences

        Returns:
            Generated text
        """
        if not self._loaded:
            self.load_model()

        if stop is None:
            stop = ["</s>", "\n\nUser:", "\n\n---"]

        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.model(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                stop=stop,
                echo=False,
                stream=False,
            )
        )

        text = response['choices'][0]['text']
        return text.strip()

    async def generate_structured(
        self,
        prompt: str,
        response_model: Type[T],
        max_tokens: int = 200,
        temperature: float = 0.7,
    ) -> T:
        """
        Generate structured output conforming to Pydantic model.

        Args:
            prompt: Input prompt with instructions to output JSON
            response_model: Pydantic model class for validation
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            Validated Pydantic model instance
        """
        # Add JSON formatting instruction
        json_prompt = f"""{prompt}

Respond with valid JSON matching this schema:
{response_model.model_json_schema()}

JSON response:
"""

        # Generate with JSON stop sequences
        response_text = await self.generate(
            prompt=json_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            stop=["\n\n", "```"]
        )

        # Parse and validate
        try:
            # Extract JSON if wrapped in markdown code blocks
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]

            data = json.loads(response_text)
            return response_model.model_validate(data)
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.debug(f"Response text: {response_text}")
            raise ValueError(f"Invalid JSON response from LLM: {e}")

    async def generate_batch(
        self,
        prompts: list[str],
        max_tokens: int = 200,
        temperature: float = 0.7,
    ) -> list[str]:
        """
        Generate completions for multiple prompts.

        Note: llama.cpp processes these sequentially, but we can
        parallelize across multiple model instances if needed.

        Args:
            prompts: List of input prompts
            max_tokens: Maximum tokens per completion
            temperature: Sampling temperature

        Returns:
            List of generated texts
        """
        # For now, process sequentially
        # TODO: Implement actual batching with multiple model instances
        results = []
        for prompt in prompts:
            result = await self.generate(
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature
            )
            results.append(result)

        return results

    def get_context_usage(self, prompt: str) -> dict[str, int]:
        """
        Estimate token count for prompt.

        Returns:
            Dictionary with token counts and remaining capacity
        """
        if not self._loaded:
            self.load_model()

        # Tokenize to get accurate count
        tokens = self.model.tokenize(prompt.encode('utf-8'))
        token_count = len(tokens)

        return {
            "used_tokens": token_count,
            "max_tokens": settings.llm_context_size,
            "remaining_tokens": settings.llm_context_size - token_count,
            "usage_percent": (token_count / settings.llm_context_size) * 100
        }

    def unload_model(self) -> None:
        """Unload model from memory."""
        if self._loaded and self.model is not None:
            del self.model
            self.model = None
            self._loaded = False
            logger.info("Model unloaded")


# Global LLM client instance
llm_client = LLMClient()
