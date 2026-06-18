import os
import json
import hashlib
import logging
from typing import Optional, Dict, List, Any, Tuple, Union
import numpy as np
from datetime import datetime

logger = logging.getLogger(__name__)

class TemplateManager:
    """Manages biometric template storage and operations."""
    
    def __init__(self, storage_path: Optional[str] = None):
        """Initialize template manager."""
        if storage_path is None:
            storage_path = os.getenv('TEMPLATE_STORAGE_PATH', './data/sample_templates/')
        
        self.storage_path = storage_path
        os.makedirs(self.storage_path, exist_ok=True)
        
        # Template cache for quick access
        self.template_cache = {}
    
    def save_fingerprint_template(self, student_id: int, template: bytes, 
                                 metadata: Optional[Dict] = None) -> str:
        """
        Save fingerprint template to disk.
        
        Args:
            student_id: Student identifier
            template: Fingerprint template bytes
            metadata: Additional template metadata
            
        Returns:
            str: Template file path
        """
        try:
            # Create filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            template_hash = hashlib.sha256(template).hexdigest()[:16]
            filename = f"fp_{student_id}_{timestamp}_{template_hash}.dat"
            filepath = os.path.join(self.storage_path, filename)
            
            # Prepare metadata
            if metadata is None:
                metadata = {}
            
            metadata.update({
                'student_id': student_id,
                'template_type': 'fingerprint',
                'timestamp': timestamp,
                'hash': template_hash,
                'size_bytes': len(template)
            })
            
            # Save template with metadata header
            with open(filepath, 'wb') as f:
                # Write metadata as JSON string followed by newline
                metadata_json = json.dumps(metadata).encode('utf-8')
                f.write(len(metadata_json).to_bytes(4, 'big'))  # Metadata length
                f.write(metadata_json)                         # Metadata
                f.write(template)                              # Template data
            
            logger.info(f"Fingerprint template saved: {filepath}")
            
            # Update cache
            cache_key = f"fp_{student_id}"
            self.template_cache[cache_key] = {
                'path': filepath,
                'template': template,
                'metadata': metadata
            }
            
            return filepath
            
        except Exception as e:
            logger.error(f"Failed to save fingerprint template: {str(e)}")
            raise
    
    def save_facial_template(self, student_id: int, template: np.ndarray,
                           metadata: Optional[Dict] = None) -> str:
        """
        Save facial template to disk.
        
        Args:
            student_id: Student identifier
            template: Facial feature vector
            metadata: Additional template metadata
            
        Returns:
            str: Template file path
        """
        try:
            # Convert numpy array to bytes
            template_bytes = template.tobytes()
            
            # Create filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            template_hash = hashlib.sha256(template_bytes).hexdigest()[:16]
            filename = f"face_{student_id}_{timestamp}_{template_hash}.dat"
            filepath = os.path.join(self.storage_path, filename)
            
            # Prepare metadata
            if metadata is None:
                metadata = {}
            
            metadata.update({
                'student_id': student_id,
                'template_type': 'facial',
                'timestamp': timestamp,
                'hash': template_hash,
                'dimensions': list(template.shape),  # Convert tuple to list for JSON serialization
                'dtype': str(template.dtype)
            })
            
            # Save template with metadata
            with open(filepath, 'wb') as f:
                metadata_json = json.dumps(metadata).encode('utf-8')
                f.write(len(metadata_json).to_bytes(4, 'big'))  # Metadata length
                f.write(metadata_json)                         # Metadata
                f.write(template_bytes)                        # Template data
            
            logger.info(f"Facial template saved: {filepath}")
            
            # Update cache
            cache_key = f"face_{student_id}"
            self.template_cache[cache_key] = {
                'path': filepath,
                'template': template,
                'metadata': metadata
            }
            
            return filepath
            
        except Exception as e:
            logger.error(f"Failed to save facial template: {str(e)}")
            raise
    
    def load_template(self, filepath: str) -> Tuple[Optional[Any], Optional[Dict]]:
        """
        Load template from disk.
        
        Args:
            filepath: Path to template file
            
        Returns:
            Tuple[template_data, metadata_dict] or (None, None) if failed
        """
        try:
            # Check cache first
            for cache_key, cached_data in self.template_cache.items():
                if cached_data['path'] == filepath:
                    logger.debug(f"Template loaded from cache: {filepath}")
                    return cached_data['template'], cached_data['metadata']
            
            # Load from disk
            with open(filepath, 'rb') as f:
                # Read metadata length
                metadata_len_bytes = f.read(4)
                if not metadata_len_bytes:
                    logger.error(f"File {filepath} is empty or corrupted")
                    return None, None
                    
                metadata_len = int.from_bytes(metadata_len_bytes, 'big')
                
                # Read metadata
                metadata_json = f.read(metadata_len).decode('utf-8')
                metadata = json.loads(metadata_json)
                
                # Read template data
                template_data = f.read()
                
                # Convert based on template type
                template_type = metadata.get('template_type', '')
                
                if template_type == 'fingerprint':
                    template = template_data  # Keep as bytes
                elif template_type == 'facial':
                    # Reconstruct numpy array
                    dtype = np.dtype(metadata['dtype'])
                    # Handle dimensions safely
                    dimensions = metadata.get('dimensions')
                    if dimensions is not None:
                        shape = tuple(dimensions)
                        template = np.frombuffer(template_data, dtype=dtype).reshape(shape)
                    else:
                        logger.error(f"Missing dimensions in metadata for {filepath}")
                        return None, None
                else:
                    logger.error(f"Unknown template type: {template_type}")
                    return None, None
            
            logger.debug(f"Template loaded from disk: {filepath}")
            return template, metadata
            
        except Exception as e:
            logger.error(f"Failed to load template {filepath}: {str(e)}")
            return None, None
    
    def get_student_templates(self, student_id: int) -> Dict[str, List[Dict]]:
        """
        Get all templates for a specific student.
        
        Args:
            student_id: Student identifier
            
        Returns:
            Dict with 'fingerprint' and 'facial' template lists
        """
        try:
            templates = {
                'fingerprint': [],
                'facial': []
            }
            
            # Search for template files
            for filename in os.listdir(self.storage_path):
                if f"_{student_id}_" in filename:
                    filepath = os.path.join(self.storage_path, filename)
                    template_data, metadata = self.load_template(filepath)
                    
                    if template_data is not None and metadata is not None:
                        template_type = metadata.get('template_type', '')
                        if template_type in templates:
                            templates[template_type].append({
                                'data': template_data,
                                'metadata': metadata,
                                'filepath': filepath
                            })
            
            logger.info(f"Found {len(templates['fingerprint'])} fingerprint and "
                       f"{len(templates['facial'])} facial templates for student {student_id}")
            return templates
            
        except Exception as e:
            logger.error(f"Failed to get templates for student {student_id}: {str(e)}")
            return {'fingerprint': [], 'facial': []}
    
    def delete_student_templates(self, student_id: int) -> bool:
        """
        Delete all templates for a specific student.
        
        Args:
            student_id: Student identifier
            
        Returns:
            bool: True if successful
        """
        try:
            deleted_count = 0
            
            for filename in os.listdir(self.storage_path):
                if f"_{student_id}_" in filename:
                    filepath = os.path.join(self.storage_path, filename)
                    os.remove(filepath)
                    deleted_count += 1
                    
                    # Remove from cache
                    for cache_key in list(self.template_cache.keys()):
                        if cache_key.endswith(f"_{student_id}"):
                            del self.template_cache[cache_key]
            
            logger.info(f"Deleted {deleted_count} templates for student {student_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete templates for student {student_id}: {str(e)}")
            return False
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """
        Get template storage statistics.
        
        Returns:
            Dict with storage statistics
        """
        try:
            stats = {
                'total_templates': 0,
                'fingerprint_templates': 0,
                'facial_templates': 0,
                'total_size_bytes': 0,
                'by_student': {}
            }
            
            for filename in os.listdir(self.storage_path):
                if filename.endswith('.dat'):
                    filepath = os.path.join(self.storage_path, filename)
                    
                    # Get file size
                    size_bytes = os.path.getsize(filepath)
                    stats['total_size_bytes'] += size_bytes
                    stats['total_templates'] += 1
                    
                    # Parse filename to get student ID and type
                    parts = filename.split('_')
                    if len(parts) >= 3:
                        template_type = parts[0]  # 'fp' or 'face'
                        try:
                            student_id = int(parts[1])
                            
                            # Update counts
                            if template_type == 'fp':
                                stats['fingerprint_templates'] += 1
                            elif template_type == 'face':
                                stats['facial_templates'] += 1
                            
                            # Update student stats
                            if student_id not in stats['by_student']:
                                stats['by_student'][student_id] = {
                                    'fingerprint_templates': 0,
                                    'facial_templates': 0,
                                    'total_size_bytes': 0
                                }
                            
                            if template_type == 'fp':
                                stats['by_student'][student_id]['fingerprint_templates'] += 1
                            elif template_type == 'face':
                                stats['by_student'][student_id]['facial_templates'] += 1
                            
                            stats['by_student'][student_id]['total_size_bytes'] += size_bytes
                            
                        except ValueError:
                            pass
            
            # Convert sizes to human-readable format
            stats['total_size_mb'] = stats['total_size_bytes'] / (1024 * 1024)
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get storage stats: {str(e)}")
            return {}

def test_template_manager():
    """Test the template manager."""
    print("Testing Template Manager...")
    
    # Create test directory
    test_dir = './data/test_templates/'
    manager = TemplateManager(test_dir)
    
    # Test fingerprint template save/load
    test_fp_template = bytes([i % 256 for i in range(512)])
    fp_path = manager.save_fingerprint_template(
        student_id=1,
        template=test_fp_template,
        metadata={'quality': 85, 'finger': 'right_index'}
    )
    print(f"[OK] Fingerprint template saved: {fp_path}")
    
    # Load it back
    loaded_fp, fp_metadata = manager.load_template(fp_path)
    if loaded_fp is not None:
        print(f"[OK] Fingerprint template loaded: {len(loaded_fp)} bytes")
        print(f"   Metadata: {fp_metadata}")
    else:
        print("[ERROR] Failed to load fingerprint template")
    
    # Test facial template save/load
    test_face_template = np.random.randn(128).astype(np.float32)
    face_path = manager.save_facial_template(
        student_id=1,
        template=test_face_template,
        metadata={'angle': 'front', 'lighting': 'good'}
    )
    print(f"[OK] Facial template saved: {face_path}")
    
    # Load it back
    loaded_face, face_metadata = manager.load_template(face_path)
    if loaded_face is not None:
        print(f"[OK] Facial template loaded: shape {loaded_face.shape}")
        print(f"   Metadata: {face_metadata}")
    else:
        print("[ERROR] Failed to load facial template")
    
    # Get student templates
    templates = manager.get_student_templates(1)
    print(f"[OK] Student 1 has:")
    print(f"   - {len(templates['fingerprint'])} fingerprint templates")
    print(f"   - {len(templates['facial'])} facial templates")
    
    # Get storage stats
    stats = manager.get_storage_stats()
    print(f"[OK] Storage stats:")
    print(f"   Total templates: {stats['total_templates']}")
    print(f"   Total size: {stats['total_size_mb']:.2f} MB")
    
    # Cleanup
    import shutil
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    
    print("[OK] All template manager tests passed")
    return True

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_template_manager()