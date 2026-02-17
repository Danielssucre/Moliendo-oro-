
import os

def check_log_status(filepath):
    if not os.path.exists(filepath):
        print("Log file not found.")
        return

    file_size = os.path.getsize(filepath)
    block_size = 1024 * 1024  # 1MB
    
    last_iteration = None
    best_pf = None
    
    with open(filepath, 'rb') as f:
        # Start from end
        pos = file_size
        
        while pos > 0 and (last_iteration is None or best_pf is None):
            read_size = min(block_size, pos)
            pos -= read_size
            f.seek(pos)
            data = f.read(read_size)
            
            # Decode carefully (ignore errors at boundaries)
            text = data.decode('utf-8', errors='ignore')
            lines = text.split('\n')
            
            # Search backwards for last iteration
            if last_iteration is None:
                for line in reversed(lines):
                    if "🧪 ITERATION" in line:
                        last_iteration = line.strip()
                        break
            
            # Search backwards for best PF
            if best_pf is None:
                for line in reversed(lines):
                    if "🏆 New best PF" in line:
                        best_pf = line.strip()
                        break
                        
            # Also check if optimization finished successfully
            for line in reversed(lines):
                if "🎯 OPTIMIZATION SUCCESSFUL" in line:
                    print(line.strip())
                    return

    print(f"Current Status:")
    print(f"{last_iteration}")
    print(f"{best_pf}")

if __name__ == "__main__":
    check_log_status("logs/optimizer_run.log")
