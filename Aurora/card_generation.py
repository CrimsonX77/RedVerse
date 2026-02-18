"""
Aurora Archive - Card Generation Module
Dual Backend Support: Grok API (xAI) + Local Stable Diffusion
"""

import os
import asyncio
import aiohttp
import base64
import time
import logging
from enum import Enum
from typing import Optional, Dict, List, Tuple, Callable
from pathlib import Path
from datetime import datetime
try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*args, **kwargs):
        import warnings
        warnings.warn("python-dotenv is not installed. Environment variables from .env will not be loaded.")

# Load environment variables from sd_config.env
load_dotenv('sd_config.env')
load_dotenv()  # Also load .env if exists (will override sd_config.env)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/card_generation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class GenerationBackend(Enum):
    """Available image generation backends"""
    GROK = "grok"
    STABLE_DIFFUSION = "stable_diffusion"


class MembershipTier(Enum):
    """Membership tier constraints"""
    KIDS = "Kids"
    STANDARD = "Standard"
    PREMIUM = "Premium"


class CardGenerator:
    """
    Main card generation class with dual backend support.
    Supports both Grok API and local Stable Diffusion WebUI.
    """
    
    # Tier-based constraints
    TIER_CONSTRAINTS = {
        MembershipTier.KIDS: {
            'max_daily_generations': 5,
            'max_file_size_mb': 5,
            'allow_custom_prompts': False,
            'allow_nsfw': False,
            'allow_animation': False,
            'safety_level': 'maximum',
            'whitelist_only': True,
        },
        MembershipTier.STANDARD: {
            'max_daily_generations': 3,
            'max_file_size_mb': 10,
            'allow_custom_prompts': True,  # Template-based only
            'allow_nsfw': True,
            'allow_animation': False,
            'safety_level': 'high',
            'whitelist_only': False,
        },
        MembershipTier.PREMIUM: {
            'max_daily_generations': -1,  # Unlimited
            'max_file_size_mb': 25,
            'allow_custom_prompts': True,
            'allow_nsfw': True,  # Age-verified only
            'allow_animation': True,
            'safety_level': 'medium',
            'whitelist_only': False,
        }
    }
    
    # Kids tier whitelisted prompts
    KIDS_WHITELIST = [
        "cute fantasy character",
        "friendly dragon",
        "magical unicorn",
        "brave knight",
        "wise wizard",
        "cheerful fairy",
        "gentle giant",
        "playful puppy",
        "curious kitten",
        "happy robot"
    ]
    
    # Standard tier curated templates
    STANDARD_TEMPLATES = {
        'Fantasy': [
            "mystical {character} with {color} elements, fantasy art style",
            "epic {character} surrounded by magical energy, detailed illustration",
            "ethereal {character} in enchanted forest, vibrant colors"
        ],
        'Sci-Fi': [
            "futuristic {character} with cybernetic enhancements, neon lighting",
            "space explorer {character} in advanced armor, cosmic background",
            "holographic {character} projection, high-tech aesthetic"
        ],
        'Anime': [
            "anime-style {character} with dynamic pose, cel-shaded",
            "manga-inspired {character} with expressive features, vibrant",
            "chibi-style {character} with oversized features, cute"
        ],
        'Realistic': [
            "photorealistic {character} portrait, studio lighting",
            "detailed {character} character study, cinematic quality",
            "realistic {character} illustration, professional artwork"
        ]
    }
    
    def __init__(
        self,
        backend: str = 'grok',
        tier: str = 'Premium',
        user_id: Optional[str] = None
    ):
        """
        Initialize the card generator.
        
        Args:
            backend: 'grok' or 'stable_diffusion'
            tier: 'Kids', 'Standard', or 'Premium'
            user_id: User identifier for tracking generations
        """
        self.backend = GenerationBackend(backend)
        self.tier = MembershipTier(tier)
        self.user_id = user_id or "anonymous"
        
        # API configuration - check multiple sources
        # Priority: 1. GROK_API_KEY, 2. XAI_API_KEY, 3. empty
        self.grok_api_key = os.getenv('GROK_API_KEY') or os.getenv('XAI_API_KEY') or ''
        self.grok_base_url = os.getenv('GROK_BASE_URL', 'https://api.x.ai/v1')
        self.sd_url = os.getenv('STABLE_DIFFUSION_URL', 'http://localhost:7860')
        
        # Log which key source was used (without revealing the key)
        if os.getenv('GROK_API_KEY'):
            logger.info("Using GROK_API_KEY from environment")
        elif os.getenv('XAI_API_KEY'):
            logger.info("Using XAI_API_KEY from environment")
        else:
            logger.warning("No Grok API key found in environment")
        
        # SD Configuration (from sd_config.env or defaults)
        self.sd_model = os.getenv('SD_MODEL_CHECKPOINT', 'AetherCrown.safetensors')
        self.sd_sampler = os.getenv('SAMPLER_NAME', 'Euler A Automatic')
        self.sd_clip_skip = int(os.getenv('CLIP_SKIP', '2'))
        self.sd_enable_hr = os.getenv('ENABLE_HIRES_FIX', 'False').lower() == 'true'
        self.sd_hr_upscaler = os.getenv('HR_UPSCALER', 'R-ESRGAN 4x+ Anime6B')
        self.sd_hr_scale = float(os.getenv('HR_SCALE', '2.0'))
        
        # Output directory
        self.output_dir = Path('Assets/generated_cards')
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generation tracking
        self.generation_count = 0
        self.session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Custom overrides (can be set after initialization)
        self.custom_steps = None
        self.custom_cfg = None
        self.custom_width = None
        self.custom_height = None
        
        logger.info(
            f"CardGenerator initialized: backend={backend}, tier={tier}, "
            f"user={self.user_id}"
        )
    
    def set_grok_api_key(self, api_key: str):
        """
        Dynamically set or update the Grok API key.
        
        Args:
            api_key: The Grok API key (should start with 'xai-')
        """
        if api_key and api_key.startswith('xai-'):
            self.grok_api_key = api_key
            logger.info("Grok API key updated successfully")
        else:
            logger.warning(f"Invalid Grok API key format. Should start with 'xai-'")
    
    async def generate_static_card(
        self,
        prompt: str,
        style: str = 'Fantasy',
        color_palette: str = 'Crimson & Gold',
        progress_callback: Optional[Callable[[str, int], None]] = None
    ) -> Dict:
        """
        Generate a static card image.
        
        Args:
            prompt: Character description or template selection
            style: Art style (Fantasy, Sci-Fi, Anime, Realistic)
            color_palette: Color scheme
            progress_callback: Optional callback(message, percentage)
            
        Returns:
            Dict with 'success', 'path', 'metadata', 'error'
        """
        try:
            if progress_callback:
                progress_callback("Validating prompt...", 10)
            
            # Validate prompt against tier restrictions
            validation = self.validate_prompt(prompt, self.tier)
            if not validation['valid']:
                return {
                    'success': False,
                    'error': validation['reason'],
                    'path': None,
                    'metadata': None
                }
            
            if progress_callback:
                progress_callback("Building generation parameters...", 20)
            
            # Build full prompt from template or custom
            full_prompt = self._build_prompt(prompt, style, color_palette)
            
            # Apply tier constraints
            params = self.apply_tier_constraints({
                'prompt': full_prompt,
                'style': style,
                'color_palette': color_palette
            }, self.tier)
            
            if progress_callback:
                progress_callback(f"Generating with {self.backend.value}...", 30)
            
            # Try primary backend
            result = await self._generate_with_backend(
                self.backend, params, progress_callback
            )
            
            # Fallback logic
            if not result['success'] and self.backend == GenerationBackend.GROK:
                logger.warning("Grok generation failed, falling back to Stable Diffusion")
                if progress_callback:
                    progress_callback("Trying fallback backend...", 50)
                result = await self._generate_with_backend(
                    GenerationBackend.STABLE_DIFFUSION, params, progress_callback
                )
            
            if result['success']:
                if progress_callback:
                    progress_callback("Finalizing...", 95)
                
                # Save metadata
                metadata = {
                    'prompt': full_prompt,
                    'style': style,
                    'color_palette': color_palette,
                    'tier': self.tier.value,
                    'backend': result['backend'],
                    'generation_time': result.get('generation_time', 0),
                    'file_size_mb': result.get('file_size_mb', 0),
                    'timestamp': datetime.now().isoformat(),
                    'user_id': self.user_id,
                    'session_id': self.session_id
                }
                
                self._log_generation(metadata)
                
                if progress_callback:
                    progress_callback("Complete!", 100)
                
                return {
                    'success': True,
                    'path': result['path'],
                    'metadata': metadata,
                    'error': None
                }
            
            return result
            
        except Exception as e:
            logger.error(f"Generation error: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': f"Generation failed: {str(e)}",
                'path': None,
                'metadata': None
            }
    
    async def generate_animated_card(
        self,
        prompt: str,
        duration: int = 5,
        effects: List[str] = None,
        progress_callback: Optional[Callable[[str, int], None]] = None
    ) -> Dict:
        """
        Generate an animated card (Premium tier only).
        
        Args:
            prompt: Character description
            duration: Animation duration in seconds (3-10)
            effects: List of animation effects
            progress_callback: Optional callback(message, percentage)
            
        Returns:
            Dict with 'success', 'path', 'metadata', 'error'
        """
        # Check tier permission
        if self.tier != MembershipTier.PREMIUM:
            return {
                'success': False,
                'error': 'Animated cards are only available for Premium members',
                'path': None,
                'metadata': None
            }
        
        # Note: Grok doesn't currently support video generation natively
        # This would require generating static image with Grok, then
        # animating locally with tools like FFmpeg or Manim
        
        try:
            if progress_callback:
                progress_callback("Generating base image...", 10)
            
            # First generate static image
            static_result = await self.generate_static_card(
                prompt, progress_callback=lambda msg, pct: 
                progress_callback(msg, int(10 + pct * 0.5))
            )
            
            if not static_result['success']:
                return static_result
            
            if progress_callback:
                progress_callback("Creating animation...", 60)
            
            # Animate the static image
            animated_path = await self._create_animation(
                static_result['path'],
                duration,
                effects or ['fade', 'particle'],
                progress_callback
            )
            
            metadata = static_result['metadata'].copy()
            metadata.update({
                'animated': True,
                'duration': duration,
                'effects': effects,
                'static_path': static_result['path']
            })
            
            if progress_callback:
                progress_callback("Complete!", 100)
            
            return {
                'success': True,
                'path': animated_path,
                'metadata': metadata,
                'error': None
            }
            
        except Exception as e:
            logger.error(f"Animation error: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': f"Animation failed: {str(e)}",
                'path': None,
                'metadata': None
            }
    
    def validate_prompt(self, prompt: str, tier: MembershipTier) -> Dict:
        """
        Validate prompt against tier restrictions.
        
        Args:
            prompt: User-provided prompt
            tier: Membership tier
            
        Returns:
            Dict with 'valid' and 'reason'
        """
        constraints = self.TIER_CONSTRAINTS[tier]
        
        # Kids tier - whitelist only
        if tier == MembershipTier.KIDS:
            if prompt.lower() not in [p.lower() for p in self.KIDS_WHITELIST]:
                return {
                    'valid': False,
                    'reason': f"Please choose from kid-friendly options: {', '.join(self.KIDS_WHITELIST[:5])}..."
                }
        
        # Standard tier - templates only
        elif tier == MembershipTier.STANDARD:
            if not constraints['allow_custom_prompts']:
                # Check if prompt matches a template pattern
                if not any(style in prompt for style in self.STANDARD_TEMPLATES.keys()):
                    return {
                        'valid': False,
                        'reason': 'Standard tier supports curated templates only. Please select a style template.'
                    }
        
        # Content safety checks (all tiers)
        nsfw_keywords = ['nude', 'naked', 'explicit', 'nsfw', 'sexual']
        if not constraints['allow_nsfw']:
            if any(keyword in prompt.lower() for keyword in nsfw_keywords):
                return {
                    'valid': False,
                    'reason': 'Content not allowed. Please use appropriate descriptions.'
                }
        
        # Violence/inappropriate content
        inappropriate = ['gore', 'blood', 'violent', 'weapon', 'gun']
        if tier == MembershipTier.KIDS:
            if any(keyword in prompt.lower() for keyword in inappropriate):
                return {
                    'valid': False,
                    'reason': 'This content is not suitable for Kids tier.'
                }
        
        return {'valid': True, 'reason': None}
    
    def apply_tier_constraints(self, params: Dict, tier: MembershipTier) -> Dict:
        """
        Apply generation constraints based on membership tier.
        
        Args:
            params: Base generation parameters
            tier: Membership tier
            
        Returns:
            Modified parameters with tier constraints
        """
        constraints = self.TIER_CONSTRAINTS[tier]
        
        # Add safety prompts
        if constraints['safety_level'] == 'maximum':
            params['negative_prompt'] = (
                "inappropriate, scary, violent, dark, disturbing, "
                "unsafe, mature content, "
                "no border, missing border, borderless, plain edges, cut off border, faded border"
            )
            params['safety_scale'] = 1.5
        elif constraints['safety_level'] == 'high':
            params['negative_prompt'] = (
                "inappropriate, explicit, nsfw, unsafe content, "
                "no border, missing border, borderless, plain edges, cut off border, faded border"
            )
            params['safety_scale'] = 1.2
        else:
            params['negative_prompt'] = "low quality, blurry, distorted, no border, missing border, borderless, plain edges, cut off border, faded border"
            params['safety_scale'] = 1.0
        
        # Quality settings based on tier
        if tier == MembershipTier.PREMIUM:
            params['quality'] = 'hd'
            params['steps'] = 50
            params['guidance_scale'] = 7.5
        elif tier == MembershipTier.STANDARD:
            params['quality'] = 'standard'
            params['steps'] = 30
            params['guidance_scale'] = 7.0
        else:  # Kids
            params['quality'] = 'standard'
            params['steps'] = 20
            params['guidance_scale'] = 6.0
        
        # File size limit
        params['max_file_size_mb'] = constraints['max_file_size_mb']
        
        return params
    
    async def check_backend_availability(self) -> Dict[str, bool]:
        """
        Test availability of both backends.
        
        Returns:
            Dict with backend names as keys and availability as values
        """
        results = {}
        
        # Test Grok
        try:
            results['grok'] = await self._test_grok_connection()
        except Exception as e:
            logger.error(f"Grok availability check failed: {e}")
            results['grok'] = False
        
        # Test Stable Diffusion
        try:
            results['stable_diffusion'] = await self._test_sd_connection()
        except Exception as e:
            logger.error(f"SD availability check failed: {e}")
            results['stable_diffusion'] = False
        
        return results
    
    def _build_prompt(
        self,
        prompt: str,
        style: str,
        color_palette: str
    ) -> str:
        """Build full prompt from template or custom input."""
        
        # For Standard tier, use templates
        if self.tier == MembershipTier.STANDARD:
            templates = self.STANDARD_TEMPLATES.get(style, [])
            if templates:
                template = templates[0]  # Use first template
                full_prompt = template.format(
                    character=prompt,
                    color=color_palette.split('&')[0].strip().lower()
                )
            else:
                full_prompt = prompt
        else:
            full_prompt = prompt
        
        # Add style and color guidance
        full_prompt += f", {style.lower()} style, {color_palette.lower()} color scheme"
        
        # Add quality modifiers with HEAVILY EMPHASIZED BORDER
        # Using multiple emphasis techniques to ensure border visibility:
        # 1. High weight (1.8) to prioritize border over other elements
        # 2. Multiple related terms for consistency
        # 3. Positioned before other quality tags
        full_prompt += ", ((ornate Trading-Card border:1.8)), ((decorative frame border:1.7)), ((intricate mystical border pattern:1.6)), arcane tribal border design"
        full_prompt += f", border color matching {color_palette.lower()} theme"
        full_prompt += ", high quality, detailed, professional artwork, Trading-card game art, TCG style, sharp focus, vibrant colors, ((Masterpiece:1.5))"
        
        return full_prompt
    
    async def _generate_with_backend(
        self,
        backend: GenerationBackend,
        params: Dict,
        progress_callback: Optional[Callable] = None
    ) -> Dict:
        """Generate image using specified backend."""
        
        start_time = time.time()
        
        if backend == GenerationBackend.GROK:
            result = await self._generate_with_grok(params, progress_callback)
        else:
            result = await self._generate_with_sd(params, progress_callback)
        
        if result['success']:
            result['generation_time'] = time.time() - start_time
            result['backend'] = backend.value
        
        return result
    
    async def _generate_with_grok(
        self,
        params: Dict,
        progress_callback: Optional[Callable] = None
    ) -> Dict:
        """
        Generate image using Grok API.
        Uses /v1/images/generations endpoint.
        """
        if not self.grok_api_key or self.grok_api_key == 'your_key_here':
            return {
                'success': False,
                'error': 'Grok API key not configured',
                'path': None
            }
        
        try:
            if progress_callback:
                progress_callback("Connecting to Grok API...", 40)
            
            headers = {
                'Authorization': f'Bearer {self.grok_api_key}',
                'Content-Type': 'application/json'
            }
            
            # Grok image generation API payload
            # Note: Grok-2-image-1212 has limited parameters - just model, prompt, n
            payload = {
                'model': 'grok-2-image-1212',
                'prompt': params['prompt'],
                'n': 1,
                'response_format': 'b64_json'
            }
            
            if progress_callback:
                progress_callback("Generating with Grok...", 60)
            
            timeout = aiohttp.ClientTimeout(total=120)  # 2 minute timeout
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    f'{self.grok_base_url}/images/generations',
                    headers=headers,
                    json=payload
                ) as response:
                    
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Grok API error: {response.status} - {error_text}")
                        return {
                            'success': False,
                            'error': f'Grok API error: {response.status}',
                            'path': None
                        }
                    
                    if progress_callback:
                        progress_callback("Downloading image...", 80)
                    
                    data = await response.json()
                    
                    # Extract image data
                    image_data = data['data'][0]['b64_json']
                    image_bytes = base64.b64decode(image_data)
                    
                    # Save image
                    filename = f"card_{self.session_id}_{self.generation_count:04d}.png"
                    filepath = self.output_dir / filename
                    
                    with open(filepath, 'wb') as f:
                        f.write(image_bytes)
                    
                    file_size_mb = len(image_bytes) / (1024 * 1024)
                    
                    if progress_callback:
                        progress_callback("Image saved!", 90)
                    
                    self.generation_count += 1
                    
                    return {
                        'success': True,
                        'path': str(filepath),
                        'file_size_mb': file_size_mb,
                        'error': None
                    }
        
        except asyncio.TimeoutError:
            logger.error("Grok API timeout")
            return {
                'success': False,
                'error': 'Generation timeout - please try again',
                'path': None
            }
        except Exception as e:
            logger.error(f"Grok generation error: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': f'Grok error: {str(e)}',
                'path': None
            }
    
    def _get_tier_sd_settings(self) -> Dict:
        """Get Stable Diffusion settings based on membership tier."""
        
        tier_configs = {
            MembershipTier.KIDS: {
                'steps': int(os.getenv('KIDS_STEPS', '20')),
                'hr_steps': int(os.getenv('KIDS_HR_STEPS', '10')),
                'denoising': float(os.getenv('KIDS_DENOISING', '0.3'))
            },
            MembershipTier.STANDARD: {
                'steps': int(os.getenv('STANDARD_STEPS', '20')),
                'hr_steps': int(os.getenv('STANDARD_HR_STEPS', '20')),
                'denoising': float(os.getenv('STANDARD_DENOISING', '0.4'))
            },
            MembershipTier.PREMIUM: {
                'steps': int(os.getenv('PREMIUM_STEPS', '40')),
                'hr_steps': int(os.getenv('PREMIUM_HR_STEPS', '30')),
                'denoising': float(os.getenv('PREMIUM_DENOISING', '0.5'))
            }
        }
        
        return tier_configs.get(self.tier, tier_configs[MembershipTier.STANDARD])
    
    async def _generate_with_sd(
        self,
        params: Dict,
        progress_callback: Optional[Callable] = None
    ) -> Dict:
        """Generate image using local Stable Diffusion WebUI."""
        
        try:
            if progress_callback:
                progress_callback("Connecting to Stable Diffusion...", 40)
            
            # Get tier-specific settings
            tier_settings = self._get_tier_sd_settings()
            
            # Use custom settings if provided, otherwise use tier defaults
            steps = self.custom_steps if self.custom_steps is not None else tier_settings['steps']
            cfg_scale = self.custom_cfg if self.custom_cfg is not None else params.get('guidance_scale', 7.0)
            width = self.custom_width if self.custom_width is not None else 512
            height = self.custom_height if self.custom_height is not None else 768
            
            # Stable Diffusion txt2img endpoint with optimized settings
            payload = {
                'prompt': params['prompt'],
                'negative_prompt': params.get('negative_prompt', ''),
                'steps': steps,
                'cfg_scale': cfg_scale,
                'width': width,
                'height': height,
                'sampler_name': ["Euler A", "Euler a", "Euler_Automatic"].count(self.sd_sampler) and self.sd_sampler or "Euler A",
                'seed': -1,  # Random seed
                'batch_size': 1,
                # High-res fix settings
                'enable_hr': self.sd_enable_hr,
                'hr_upscaler': self.sd_hr_upscaler,
                'hr_second_pass_steps': tier_settings['hr_steps'],
                'denoising_strength': tier_settings['denoising'],
                'hr_scale': self.sd_hr_scale,
                # Advanced settings
                'clip_skip': self.sd_clip_skip,
                # Override model checkpoint
                'override_settings': {
                    'sd_model_checkpoint': self.sd_model,
                    'CLIP_stop_at_last_layers': self.sd_clip_skip
                },
                'override_settings_restore_afterwards': True
            }
            
            if progress_callback:
                settings_info = f"Steps: {steps}, CFG: {cfg_scale}"
                progress_callback(f"Generating with {self.sd_model.split('.')[0]} ({settings_info})...", 60)
            
            timeout = aiohttp.ClientTimeout(total=180)  # 3 minute timeout
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    f'{self.sd_url}/sdapi/v1/txt2img',
                    json=payload
                ) as response:
                    
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"SD API error: {response.status} - {error_text}")
                        return {
                            'success': False,
                            'error': f'Stable Diffusion error: {response.status}',
                            'path': None
                        }
                    
                    if progress_callback:
                        progress_callback("Processing image...", 80)
                    
                    data = await response.json()
                    
                    # Extract first image
                    image_data = data['images'][0]
                    image_bytes = base64.b64decode(image_data)
                    
                    # Save image
                    filename = f"card_{self.session_id}_{self.generation_count:04d}.png"
                    filepath = self.output_dir / filename
                    
                    with open(filepath, 'wb') as f:
                        f.write(image_bytes)
                    
                    file_size_mb = len(image_bytes) / (1024 * 1024)
                    
                    if progress_callback:
                        progress_callback("Image saved!", 90)
                    
                    self.generation_count += 1
                    
                    return {
                        'success': True,
                        'path': str(filepath),
                        'file_size_mb': file_size_mb,
                        'error': None
                    }
        
        except aiohttp.ClientConnectorError:
            logger.error("Cannot connect to Stable Diffusion - is it running?")
            return {
                'success': False,
                'error': 'Cannot connect to Stable Diffusion (localhost:7860)',
                'path': None
            }
        except asyncio.TimeoutError:
            logger.error("SD API timeout")
            return {
                'success': False,
                'error': 'Generation timeout - please try again',
                'path': None
            }
        except Exception as e:
            logger.error(f"SD generation error: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': f'SD error: {str(e)}',
                'path': None
            }
    
    async def _create_animation(
        self,
        static_path: str,
        duration: int,
        effects: List[str],
        progress_callback: Optional[Callable] = None
    ) -> str:
        """
        Create animation from static image.
        Uses FFmpeg for video encoding with effects.
        """
        try:
            # This is a placeholder - would require FFmpeg integration
            # For now, just copy the static image and add metadata
            
            if progress_callback:
                progress_callback("Applying animation effects...", 70)
            
            # Simulated animation creation
            await asyncio.sleep(2)
            
            # In production, would use FFmpeg to create:
            # - Particle effects overlay
            # - Fade in/out
            # - Subtle motion (zoom, pan)
            # - Glow effects
            
            animated_filename = Path(static_path).stem + '_animated.mp4'
            animated_path = self.output_dir / animated_filename
            
            # Placeholder: copy static as fallback
            # In production: ffmpeg command here
            import shutil
            shutil.copy(static_path, animated_path.with_suffix('.png'))
            
            if progress_callback:
                progress_callback("Animation complete!", 95)
            
            return str(animated_path.with_suffix('.png'))
            
        except Exception as e:
            logger.error(f"Animation creation error: {str(e)}", exc_info=True)
            # Fallback to static image
            return static_path
    
    async def _test_grok_connection(self) -> bool:
        """Test Grok API connection."""
        if not self.grok_api_key or self.grok_api_key == 'your_key_here':
            return False
        
        try:
            headers = {'Authorization': f'Bearer {self.grok_api_key}'}
            timeout = aiohttp.ClientTimeout(total=10)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    f'{self.grok_base_url}/models',
                    headers=headers
                ) as response:
                    return response.status == 200
        except:
            return False
    
    async def _test_sd_connection(self) -> bool:
        """Test Stable Diffusion API connection."""
        try:
            timeout = aiohttp.ClientTimeout(total=5)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    f'{self.sd_url}/sdapi/v1/sd-models'
                ) as response:
                    return response.status == 200
        except:
            return False
    
    def _log_generation(self, metadata: Dict):
        """Log generation to audit trail."""
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        
        log_file = log_dir / 'generations.log'
        
        log_entry = (
            f"{metadata['timestamp']} | "
            f"User: {metadata['user_id']} | "
            f"Tier: {metadata['tier']} | "
            f"Backend: {metadata['backend']} | "
            f"Time: {metadata['generation_time']:.2f}s | "
            f"Size: {metadata['file_size_mb']:.2f}MB | "
            f"Prompt: {metadata['prompt'][:50]}...\n"
        )
        
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(log_entry)


# Helper functions for standalone use
async def test_grok_connection() -> bool:
    """Test Grok API availability."""
    generator = CardGenerator(backend='grok')
    return await generator._test_grok_connection()


async def test_sd_connection() -> bool:
    """Test Stable Diffusion local API."""
    generator = CardGenerator(backend='stable_diffusion')
    return await generator._test_sd_connection()


async def quick_generate(
    prompt: str,
    tier: str = 'Standard',
    style: str = 'Fantasy'
) -> Dict:
    """
    Quick generation function for testing.
    
    Args:
        prompt: Character description
        tier: Membership tier
        style: Art style
        
    Returns:
        Generation result dict
    """
    generator = CardGenerator(backend='grok', tier=tier)
    
    # Test availability
    availability = await generator.check_backend_availability()
    
    # Auto-select available backend
    if availability['grok']:
        generator.backend = GenerationBackend.GROK
    elif availability['stable_diffusion']:
        generator.backend = GenerationBackend.STABLE_DIFFUSION
    else:
        return {
            'success': False,
            'error': 'No backends available',
            'path': None,
            'metadata': None
        }
    
    return await generator.generate_static_card(
        prompt=prompt,
        style=style,
        color_palette='Crimson & Gold'
    )


# CLI test function
if __name__ == '__main__':
    async def main():
        print("🌅 Aurora Card Generator - Backend Test")
        print("=" * 50)
        
        # Test connections
        print("\n📡 Testing backend availability...")
        grok_ok = await test_grok_connection()
        sd_ok = await test_sd_connection()
        
        print(f"✓ Grok API: {'Available' if grok_ok else 'Unavailable'}")
        print(f"✓ Stable Diffusion: {'Available' if sd_ok else 'Unavailable'}")
        
        if not grok_ok and not sd_ok:
            print("\n⚠️  No backends available. Please check configuration.")
            return
        
        # Test generation
        print("\n🎨 Testing card generation...")
        result = await quick_generate(
            prompt="mystical warrior",
            tier="Standard",
            style="Fantasy"
        )
        
        if result['success']:
            print(f"\n✅ Generation successful!")
            print(f"📁 Saved to: {result['path']}")
            print(f"⏱️  Time: {result['metadata']['generation_time']:.2f}s")
            print(f"📦 Size: {result['metadata']['file_size_mb']:.2f}MB")
            print(f"🔧 Backend: {result['metadata']['backend']}")
        else:
            print(f"\n❌ Generation failed: {result['error']}")
    
    asyncio.run(main())
