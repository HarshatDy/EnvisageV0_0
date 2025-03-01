from img_gen import ImageGenerator
import os

def main():
    """
    Test the ImageGenerator class by generating an image from a prompt
    """
    print("Initializing ImageGenerator...")
    generator = ImageGenerator()
    
    # Basic test prompt
    test_prompt = "A futuristic city with flying cars and towering skyscrapers at sunset"
    
    print(f"Generating image with prompt: '{test_prompt}'")
    
    # Option 1: Generate directly
    result = generator.generate_image(test_prompt)
    
    # Option 2: Enhance the prompt first (uncomment to use this approach)
    # enhanced_prompt = generator.enhance_prompt(test_prompt)
    # print(f"Enhanced prompt: '{enhanced_prompt}'")
    # result = generator.generate_image(enhanced_prompt)
    
    if 'error' in result:
        print(f"Error generating image: {result['error']}")
    else:
        print("Image generation successful!")
        print(f"Image URL: {result['url']}")
        print(f"Local path: {result['local_path']}")
        
        # Check if the file exists
        if os.path.exists(result['local_path']):
            print(f"Image saved successfully to {result['local_path']}")
            print(f"File size: {os.path.getsize(result['local_path'])/1024:.2f} KB")
        else:
            print(f"Warning: Image file not found at {result['local_path']}")

if __name__ == "__main__":
    main()
