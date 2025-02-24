"""
Socket.IO Patch Utility

This module provides patches for NiceGUI's Socket.IO implementation to fix issues with
dictionary client IDs and other common problems.
"""

import sys
import types
from loguru import logger
from nicegui import app
from nicegui.client import Client
import inspect

def apply_socketio_patches():
    """Apply critical patches for Socket.IO client ID handling"""
    logger.info("Attempting to apply Socket.IO patches")
    try:
        # Patch for NiceGUI's handshake handler (found in nicegui.py)
        # Get direct access to the handshake handler through socketio event handlers
        
        if hasattr(app, 'sio') and hasattr(app.sio, 'handlers'):
            # Find the handshake handler in socketio event handlers
            handshake_handler = None
            for namespace in app.sio.handlers:
                if 'handshake' in app.sio.handlers[namespace]:
                    handshake_handler = app.sio.handlers[namespace]['handshake'][0]
                    break
            
            if handshake_handler:
                # Get the original function
                original_handler = handshake_handler
                
                # Define the patched handler
                async def patched_handshake_handler(sid, environ, *args, **kwargs):
                    try:
                        # Convert first argument (client_id) if it's a dict
                        if args and isinstance(args[0], dict):
                            client_id_dict = args[0]
                            # Create a stable string hash from the dict
                            hashable_id = str(hash(frozenset(client_id_dict.items())))
                            logger.warning(f"Converting dict client_id to hashable: {hashable_id}")
                            # Replace the dict with the hash
                            args = (hashable_id,) + args[1:]
                        
                        # Call the original handler with modified args
                        return await original_handler(sid, environ, *args, **kwargs)
                    except Exception as e:
                        logger.error(f"Error in patched handshake handler: {str(e)}")
                        return None
                
                # Replace the handler in socketio
                for namespace in app.sio.handlers:
                    if 'handshake' in app.sio.handlers[namespace]:
                        app.sio.handlers[namespace]['handshake'][0] = patched_handshake_handler
                        logger.info("Applied patch to handshake handler")
        
        # Patch Client.instances to handle dict keys
        # We need to make Client.instances a custom dictionary that converts dict keys to strings
        if hasattr(Client, 'instances'):
            original_instances = Client.instances
            
            class DictKeyHandlingDict(dict):
                def __getitem__(self, key):
                    if isinstance(key, dict):
                        key = str(hash(frozenset(key.items())))
                    return super().__getitem__(key)
                
                def get(self, key, default=None):
                    if isinstance(key, dict):
                        key = str(hash(frozenset(key.items())))
                    return super().get(key, default)
                
                def __contains__(self, key):
                    if isinstance(key, dict):
                        key = str(hash(frozenset(key.items())))
                    return super().__contains__(key)
            
            # Create new dict with same items but custom behavior
            new_instances = DictKeyHandlingDict(original_instances)
            Client.instances = new_instances
            logger.info("Applied patch to Client.instances for dict key handling")
        
        # Patch 2: Fix emit method for dictionary rooms
        if hasattr(app, 'sio') and hasattr(app.sio, 'emit'):
            original_emit = app.sio.emit
            
            def safe_emit(event, data=None, room=None, **kwargs):
                if isinstance(room, dict):
                    room = str(hash(frozenset(room.items())))
                return original_emit(event, data=data, room=room, **kwargs)
            
            # Only patch if it hasn't been patched already
            if not hasattr(app.sio, '_patched'):
                app.sio.emit = safe_emit
                app.sio._patched = True
                logger.info("Applied socketio emit patch for dictionary client IDs")
            
        return True
    except Exception as e:
        logger.error(f"Failed to apply Socket.IO patches: {str(e)}")
        logger.exception("Full traceback:")
        return False 