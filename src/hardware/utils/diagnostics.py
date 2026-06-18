"""
Hardware diagnostics utilities
"""

import time
import logging
from typing import Dict, List, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class HardwareDiagnostics:
    """Hardware diagnostics and testing"""
    
    def __init__(self, hardware_manager):
        self.hardware_manager = hardware_manager
        self.test_results = {}
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all diagnostic tests"""
        logger.info("Starting hardware diagnostics...")
        
        self.test_results = {
            "timestamp": datetime.now().isoformat(),
            "tests_run": [],
            "overall_status": "unknown",
            "summary": {}
        }
        
        # Run individual tests
        tests = [
            self.test_connectivity,
            self.test_fingerprint_scanners,
            self.test_facial_cameras,
            self.test_access_controllers,
            self.test_performance
        ]
        
        for test_func in tests:
            try:
                test_name = test_func.__name__
                logger.info(f"Running test: {test_name}")
                
                result = test_func()
                self.test_results["tests_run"].append({
                    "name": test_name,
                    "result": result
                })
                
            except Exception as e:
                logger.error(f"Test {test_func.__name__} failed: {e}")
                self.test_results["tests_run"].append({
                    "name": test_func.__name__,
                    "result": {"status": "failed", "error": str(e)}
                })
        
        # Determine overall status
        self._calculate_overall_status()
        
        logger.info(f"Diagnostics complete. Overall status: {self.test_results['overall_status']}")
        return self.test_results
    
    def test_connectivity(self) -> Dict[str, Any]:
        """Test hardware connectivity"""
        status = self.hardware_manager.get_device_status()
        
        # Count connected devices
        connected_scanners = sum(1 for s in status["fingerprint_scanners"].values() 
                               if s.get("connected", False))
        connected_cameras = sum(1 for c in status["facial_cameras"].values() 
                              if c.get("connected", False))
        connected_controllers = sum(1 for a in status["access_controllers"].values() 
                                  if a.get("connected", False))
        
        total_expected = (
            len(status["fingerprint_scanners"]) +
            len(status["facial_cameras"]) +
            len(status["access_controllers"])
        )
        
        total_connected = connected_scanners + connected_cameras + connected_controllers
        
        return {
            "status": "passed" if total_connected > 0 else "failed",
            "connected_devices": total_connected,
            "expected_devices": total_expected,
            "scanners_connected": connected_scanners,
            "cameras_connected": connected_cameras,
            "controllers_connected": connected_controllers
        }
    
    def test_fingerprint_scanners(self) -> Dict[str, Any]:
        """Test fingerprint scanners"""
        results = {}
        
        for scanner_id, scanner in self.hardware_manager.fingerprint_scanners.items():
            try:
                # Test connection
                if not scanner.is_connected():
                    results[scanner_id] = {"status": "failed", "error": "Not connected"}
                    continue
                
                # Test scan capability
                start_time = time.time()
                scan_result = scanner.scan_fingerprint(timeout=3)
                scan_time = time.time() - start_time
                
                if scan_result:
                    user_id, confidence = scan_result
                    results[scanner_id] = {
                        "status": "passed",
                        "scan_time": round(scan_time, 2),
                        "confidence": confidence,
                        "user_id": user_id
                    }
                else:
                    results[scanner_id] = {
                        "status": "warning",
                        "message": "No fingerprint detected",
                        "scan_time": round(scan_time, 2)
                    }
                    
            except Exception as e:
                results[scanner_id] = {"status": "failed", "error": str(e)}
        
        return {
            "status": "passed" if results else "failed",
            "scanners_tested": len(results),
            "details": results
        }
    
    def test_facial_cameras(self) -> Dict[str, Any]:
        """Test facial recognition cameras"""
        results = {}
        
        for camera_id, camera in self.hardware_manager.facial_cameras.items():
            try:
                # Test connection
                if not camera.is_connected():
                    results[camera_id] = {"status": "failed", "error": "Not connected"}
                    continue
                
                # Test frame capture
                start_time = time.time()
                frame = camera.get_frame()
                capture_time = time.time() - start_time
                
                if frame is not None:
                    results[camera_id] = {
                        "status": "passed",
                        "capture_time": round(capture_time, 2),
                        "frame_shape": frame.shape
                    }
                else:
                    results[camera_id] = {
                        "status": "failed",
                        "error": "Failed to capture frame"
                    }
                    
            except Exception as e:
                results[camera_id] = {"status": "failed", "error": str(e)}
        
        return {
            "status": "passed" if results else "failed",
            "cameras_tested": len(results),
            "details": results
        }
    
    def test_access_controllers(self) -> Dict[str, Any]:
        """Test access controllers"""
        results = {}
        
        for controller_id, controller in self.hardware_manager.access_controllers.items():
            try:
                # Test connection
                if not controller.is_connected():
                    results[controller_id] = {"status": "failed", "error": "Not connected"}
                    continue
                
                # Test status retrieval
                status = controller.get_status()
                
                results[controller_id] = {
                    "status": "passed",
                    "controller_type": status.get("controller_type"),
                    "is_open": status.get("is_open"),
                    "access_count": status.get("access_count")
                }
                
            except Exception as e:
                results[controller_id] = {"status": "failed", "error": str(e)}
        
        return {
            "status": "passed" if results else "failed",
            "controllers_tested": len(results),
            "details": results
        }
    
    def test_performance(self) -> Dict[str, Any]:
        """Test system performance"""
        results = {}
        
        try:
            # Test response time
            start_time = time.time()
            status = self.hardware_manager.get_device_status()
            response_time = time.time() - start_time
            
            results["response_time"] = {
                "value": round(response_time, 3),
                "unit": "seconds",
                "status": "passed" if response_time < 1.0 else "warning"
            }
            
            # Memory usage (simplified)
            import psutil
            process = psutil.Process()
            memory_usage = process.memory_info().rss / 1024 / 1024  # MB
            
            results["memory_usage"] = {
                "value": round(memory_usage, 2),
                "unit": "MB",
                "status": "passed" if memory_usage < 500 else "warning"
            }
            
            # CPU usage
            cpu_percent = process.cpu_percent(interval=0.1)
            
            results["cpu_usage"] = {
                "value": round(cpu_percent, 1),
                "unit": "%",
                "status": "passed" if cpu_percent < 80 else "warning"
            }
            
        except Exception as e:
            results["error"] = str(e)
            results["status"] = "failed"
        
        return {
            "status": "passed" if "error" not in results else "failed",
            "metrics": results
        }
    
    def _calculate_overall_status(self):
        """Calculate overall diagnostic status"""
        passed_tests = 0
        total_tests = len(self.test_results["tests_run"])
        
        for test in self.test_results["tests_run"]:
            if test["result"].get("status") == "passed":
                passed_tests += 1
        
        if total_tests == 0:
            self.test_results["overall_status"] = "unknown"
        elif passed_tests == total_tests:
            self.test_results["overall_status"] = "excellent"
        elif passed_tests >= total_tests * 0.7:
            self.test_results["overall_status"] = "good"
        elif passed_tests >= total_tests * 0.4:
            self.test_results["overall_status"] = "fair"
        else:
            self.test_results["overall_status"] = "poor"
        
        # Create summary
        self.test_results["summary"] = {
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "success_rate": round(passed_tests / total_tests * 100, 1) if total_tests > 0 else 0
        }