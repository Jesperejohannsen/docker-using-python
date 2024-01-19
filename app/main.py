import subprocess
import sys


def main():
    command = sys.argv[3]
    args = sys.argv[4:]
    
    completed_process = subprocess.run([command + args], capture_output=True)
    
    process = subprocess.Popen([command] + args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    stdout, stderr = process.communicate()
    sys.stdout.write(stdout.decode("utf-8"))
    sys.stderr.write(stderr.decode("utf-8")) 
    

if __name__ == "__main__":
    main()
