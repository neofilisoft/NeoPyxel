from abc import ABC, abstractmethod
import pygame  # only for color/rrect types, but backend should be independent

class GraphicsBackend(ABC):
    """Abstract base class for all graphics backends."""

    @abstractmethod
    def initialize(self, internal_res, screen_res, title="NeoPyxel"):
        """Set up the window and rendering surfaces."""
        pass

    @abstractmethod
    def begin_frame(self):
        """Prepare for a new frame (clear buffers, etc.)."""
        pass

    @abstractmethod
    def draw_rect(self, rect, color):
        """Draw a filled rectangle at the given pygame.Rect (in internal coordinates)."""
        pass

    @abstractmethod
    def draw_surface(self, surface, rect):
        """Draw a pygame Surface (for sprites) – only if backend supports it."""
        pass

    @abstractmethod
    def apply_lighting(self, light_mask):
        """Apply the light mask (pygame Surface with per-pixel alpha) to the frame."""
        pass

    @abstractmethod
    def draw_text(self, text, position, color, font):
        """Draw text using a pygame Font (or backend equivalent)."""
        pass

    @abstractmethod
    def end_frame(self):
        """Present the rendered frame to the screen."""
        pass

    @abstractmethod
    def get_internal_surface(self):
        """Return the internal surface (if applicable) for UI drawing."""
        pass

    @abstractmethod
    def cleanup(self):
        """Release resources."""
        pass