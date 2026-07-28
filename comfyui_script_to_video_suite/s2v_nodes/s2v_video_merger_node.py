"""
Merges video clips with smooth transitions
"""

import os
import uuid
import re
from pathlib import Path
from typing import List, Tuple
try:
    from natsort import natsorted
except ImportError:
    def natsorted(values):
        def key(value):
            return [
                int(part) if part.isdigit() else part.lower()
                for part in re.split(r"(\d+)", str(value))
            ]
        return sorted(values, key=key)

try:
    from moviepy import VideoFileClip, concatenate_videoclips
except ImportError:
    try:
        from moviepy.editor import VideoFileClip, concatenate_videoclips
    except ImportError:
        VideoFileClip = None
        concatenate_videoclips = None

import folder_paths


class VideoMergerNode:
    """
    A node that merges multiple video files with smooth transitions.
    """
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "directory_path": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "placeholder": "Path to folder containing videos"
                }),
                "transition_duration": ("FLOAT", {
                    "default": 0.5,
                    "min": 0.0,
                    "max": 5.0,
                    "step": 0.1,
                    "display": "number"
                }),
                "transition_type": (["crossfade", "none"], {
                    "default": "crossfade"
                }),
                "max_height": ("INT", {
                    "default": 1080,
                    "min": 480,
                    "max": 4320,
                    "step": 1,
                    "display": "number"
                }),
                "output_filename": ("STRING", {
                    "default": "merged_video.mp4",
                    "multiline": False
                }),
                "force_fps": ("FLOAT", {
                    "default": 0.0,
                    "min": 0.0,
                    "max": 240.0,
                    "step": 0.01,
                    "display": "number"
                }),
            }
        }
    
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("output_path",)
    FUNCTION = "merge_videos"
    CATEGORY = "Script To Video Suite/Video"
    OUTPUT_NODE = True

    def discover_videos(self, directory_path: str) -> List[Path]:
        """
        Discover and sort video files in the directory using natural sorting.
        
        Args:
            directory_path: Path to directory containing videos
            
        Returns:
            List of Path objects sorted naturally 
        """
        directory = Path(directory_path)
        
        if not directory.exists():
            raise ValueError(f"Directory does not exist: {directory_path}")
        
        if not directory.is_dir():
            raise ValueError(f"Path is not a directory: {directory_path}")
        
        # Supported video formats
        video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv'}
        
        # Find all video files
        video_files = [
            f for f in directory.iterdir()
            if f.is_file() and f.suffix.lower() in video_extensions
        ]
        
        if not video_files:
            raise ValueError(f"No video files found in: {directory_path}")
        
        # Natural sort
        sorted_videos = natsorted(video_files, key=lambda x: x.name)
        
        print(f"Found {len(sorted_videos)} video files:")
        for i, video in enumerate(sorted_videos, 1):
            print(f"  {i}. {video.name}")
        
        return sorted_videos
    
    def normalize_audio(self, clip: VideoFileClip) -> VideoFileClip:
        """
        Normalize audio to 44100 Hz to prevent pops and sync issues.
        Supports both MoviePy 1.x and 2.x APIs.
        """
        if clip.audio is not None:
            if hasattr(clip.audio, 'with_fps'):
                new_audio = clip.audio.with_fps(44100)
            else:
                new_audio = clip.audio.set_fps(44100)
                
            if hasattr(clip, 'with_audio'):
                clip = clip.with_audio(new_audio)
            else:
                clip = clip.set_audio(new_audio)
        return clip
    
    def resize_if_needed(self, clip: VideoFileClip, max_height: int) -> VideoFileClip:
        """
        Resize clip if it exceeds max_height.
        Supports both MoviePy 1.x and 2.x APIs.
        """
        if clip.h > max_height:
            print(f"  Resizing from {clip.h}p to {max_height}p to save memory")
            if hasattr(clip, 'resized'):
                clip = clip.resized(height=max_height)
            elif hasattr(clip, 'resize'):
                clip = clip.resize(height=max_height)
        return clip
    
    def merge_videos(
        self,
        directory_path: str,
        transition_duration: float,
        transition_type: str,
        max_height: int,
        output_filename: str,
        force_fps: float = 0.0
    ) -> Tuple[str]:
        """
        Main function to merge videos with transitions.
        
        Args:
            directory_path: Path to folder containing videos
            transition_duration: Duration of crossfade in seconds
            transition_type: Type of transition ("crossfade" or "none")
            max_height: Maximum resolution height
            output_filename: Name of output file
            
        Returns:
            Tuple containing path to merged video
        """
        if VideoFileClip is None or concatenate_videoclips is None:
            raise ImportError(
                "MoviePy is required only when Video Merger runs. Install it in the ComfyUI environment."
            )

        print(f"\n{'='*60}")
        print(f"Video Merger Node - Starting")
        print(f"{'='*60}")
        
        # Discover videos
        print(f"\n[1/4] Discovering videos in: {directory_path}")
        video_paths = self.discover_videos(directory_path)
        
        # Load and process clips
        print(f"\n[2/4] Loading and processing {len(video_paths)} clips...")
        clips = []
        
        try:
            for i, video_path in enumerate(video_paths, 1):
                print(f"  Loading {i}/{len(video_paths)}: {video_path.name}")
                clip = VideoFileClip(str(video_path))
                
                clip = self.normalize_audio(clip)
                
                clip = self.resize_if_needed(clip, max_height)
                
                clips.append(clip)
            
            # FPS normalization: ensure all clips have the same FPS
            if clips:
                if force_fps > 0:
                    target_fps = force_fps
                else:
                    target_fps = clips[0].fps
                
                print(f"  Normalizing all clips to {target_fps} FPS")
                normalized_clips = []
                for clip in clips:
                    if clip.fps != target_fps:
                        print(f"    Adjusting clip from {clip.fps} to {target_fps} FPS")
                        if hasattr(clip, 'with_fps'):
                            clip = clip.with_fps(target_fps)
                        else:
                            clip = clip.set_fps(target_fps)
                    normalized_clips.append(clip)
                clips = normalized_clips
        
            # Apply transitions
            print(f"\n[3/4] Applying transitions (type: {transition_type})...")
            
            if transition_type == "crossfade" and len(clips) > 1:
                min_clip_duration = min(c.duration for c in clips)
                safe_transition = min(transition_duration, min_clip_duration / 2)
                
                if safe_transition < transition_duration:
                    print(f"  Warning: Transition duration ({transition_duration}s) too long for shortest clip ({min_clip_duration}s)")
                    print(f"  Using safe duration: {safe_transition}s")
                    transition_duration = safe_transition
                
                # Use negative padding for crossfade overlap
                print(f"  Applying crossfade with {transition_duration}s overlap")
                final_clip = concatenate_videoclips(
                    clips,
                    method="compose",
                    padding=-transition_duration
                )
            else:
                final_clip = concatenate_videoclips(clips, method="compose")
        
            # Export to ComfyUI output folder
            print(f"\n[4/4] Exporting merged video...")
            
            # Get ComfyUI output directory
            output_dir = folder_paths.get_output_directory()
            output_path = os.path.join(output_dir, output_filename)
            
            # Ensure unique filename
            base_name, ext = os.path.splitext(output_filename)
            counter = 1
            while os.path.exists(output_path):
                output_path = os.path.join(output_dir, f"{base_name}_{counter}{ext}")
                counter += 1
            
            print(f"  Output path: {output_path}")
            
            # Generate a unique temporary audio filename to prevent collisions in parallel runs
            temp_audio_name = f"temp-audio-{uuid.uuid4().hex[:8]}.m4a"
            
            # Write video file with proper cleanup
            try:
                final_clip.write_videofile(
                    output_path,
                    codec='libx264',
                    audio_codec='aac',
                    temp_audiofile=temp_audio_name,
                    remove_temp=True,
                    fps=final_clip.fps
                )
            finally:
                # Clean up resources even if export fails
                final_clip.close()
                for clip in clips:
                    clip.close()
            
            print(f"\n{'='*60}")
            print(f"✓ Video merge complete!")
            print(f"  Total clips merged: {len(video_paths)}")
            print(f"  Output: {output_path}")
            print(f"{'='*60}\n")
            
            return (output_path,)
            
        except Exception as e:
            # Ensure cleanup on any error
            for clip in clips:
                try:
                    clip.close()
                except:
                    pass
            raise 
