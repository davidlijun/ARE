import random
import time
import sys

def dramatic_picker():
    names = ["于辰熙", "于辰瑶"]
    print("Choosing the perfect name...")
    
    # Simulate suspenseful "thinking"
    for i in range(10):
        temp_name = random.choice(names)
        sys.stdout.write(f"\rAnalysing: {temp_name}...")
        sys.stdout.flush()
        time.sleep(0.2 + (i * 0.1)) # Gets slower at the end
    
    final_choice = random.choice(names)
    print(f"\n\n✨ Final Decision: {final_choice} ✨")

if __name__ == "__main__":
    dramatic_picker()