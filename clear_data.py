import os
import shutil

def clear_all_data() -> None:
    """Removes all stored configuration files, environment files, and python caches."""
    files_to_remove = ["config.json", ".env"]
    dirs_to_remove = ["__pycache__"]
    
    print("GitHub Stars Manager & Remover - Clearing Data...")
    
    # Remove configuration and credential files
    for file in files_to_remove:
        if os.path.exists(file):
            try:
                os.remove(file)
                print(f"✓ Removed file: {file}")
            except Exception as e:
                print(f"✗ Failed to remove file {file}: {e}")
        else:
            print(f"· File already clear or not present: {file}")
            
    # Clean up Python compilation directories
    for directory in dirs_to_remove:
        if os.path.exists(directory):
            try:
                shutil.rmtree(directory)
                print(f"✓ Removed cache directory: {directory}")
            except Exception as e:
                print(f"✗ Failed to remove cache directory {directory}: {e}")
                
    print("Data clearance complete. The application will initialize fresh on the next launch.")

if __name__ == "__main__":
    clear_all_data()
