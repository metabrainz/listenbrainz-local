#!/usr/bin/env python3
"""
Test runner script for ListenBrainz Local.

This script provides an easy way to run tests with proper environment setup.
"""

import os
import sys
import subprocess
import tempfile
from pathlib import Path


def main():
    """Main test runner function."""
    # Get the project root directory
    project_root = Path(__file__).parent.absolute()
    
    # Set up environment variables for testing
    test_env = os.environ.copy()
    
    # Create a temporary database for testing
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
        test_db_path = tmp_db.name
    
    # Set test environment variables
    test_env.update({
        'DATABASE_FILE': test_db_path,
        'SECRET_KEY': 'test-secret-key-for-testing-only',
        'DOMAIN': 'http://localhost',
        'PORT': '5000',
        'AUTHORIZED_USERS': 'test_user,test_admin',
        'ADMIN_USERS': 'test_admin',
        'SERVICE_USERS': 'test_service',
        'MUSICBRAINZ_CLIENT_ID': 'test_client_id',
        'MUSICBRAINZ_CLIENT_SECRET': 'test_client_secret',
        'FLASK_ENV': 'testing',
        'TESTING': '1'
    })
    
    # Change to project root
    os.chdir(project_root)
    
    # Build the pytest command
    cmd = [sys.executable, '-m', 'pytest']
    
    # Add any additional arguments passed to this script
    if len(sys.argv) > 1:
        cmd.extend(sys.argv[1:])
    
    try:
        # Run the tests
        print("🧪 Running ListenBrainz Local tests...")
        print(f"📁 Project root: {project_root}")
        print(f"🗄️  Test database: {test_db_path}")
        print("=" * 60)
        
        result = subprocess.run(cmd, env=test_env)
        
        print("=" * 60)
        if result.returncode == 0:
            print("✅ All tests passed!")
        else:
            print("❌ Some tests failed!")
            
        return result.returncode
        
    except KeyboardInterrupt:
        print("\n⏸️  Tests interrupted by user")
        return 1
    except Exception as e:
        print(f"💥 Error running tests: {e}")
        return 1
    finally:
        # Clean up the temporary database
        try:
            os.unlink(test_db_path)
        except FileNotFoundError:
            pass


if __name__ == '__main__':
    sys.exit(main())
