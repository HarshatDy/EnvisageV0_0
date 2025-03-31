import unittest
from unittest import mock
from unittest.mock import MagicMock, patch
import os
import sys
import json
from io import BytesIO
from PIL import Image

# Add parent directory to path to import the ImageGenerator
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from model_api.img_gen import ImageGenerator

class TestImageGenerator(unittest.TestCase):
    @patch('model_api.img_gen.create_log_file')
    @patch('model_api.img_gen.os.path.exists')
    @patch('model_api.img_gen.os.makedirs')
    def setUp(self, mock_makedirs, mock_exists, mock_create_log):
        # Mock environment variables
        self.env_patcher = patch.dict('os.environ', {
            'ORG': 'test-org',
            'PROJ': 'test-project',
            'OPENAI_API_KEY': 'test-key'
        })
        self.env_patcher.start()
        
        # Mock OpenAI client
        self.openai_patcher = patch('model_api.img_gen.OpenAI')
        self.mock_openai = self.openai_patcher.start()
        self.mock_client = MagicMock()
        self.mock_openai.return_value = self.mock_client
        
        # Set up return values for path exists
        mock_exists.return_value = False
        
        # Create ImageGenerator instance
        self.img_gen = ImageGenerator()
        
        # Verify directory creation logic was called
        mock_makedirs.assert_called_once()
        mock_create_log.assert_called_once()

    def tearDown(self):
        self.env_patcher.stop()
        self.openai_patcher.stop()

    def test_ensure_image_directory(self):
        # Test directory creation when it doesn't exist
        with patch('model_api.img_gen.os.path.exists', return_value=False):
            with patch('model_api.img_gen.os.makedirs') as mock_makedirs:
                self.img_gen._ensure_image_directory()
                mock_makedirs.assert_called_once()
        
        # Test no directory creation when it exists
        with patch('model_api.img_gen.os.path.exists', return_value=True):
            with patch('model_api.img_gen.os.makedirs') as mock_makedirs:
                self.img_gen._ensure_image_directory()
                mock_makedirs.assert_not_called()

    @patch('model_api.img_gen.append_to_log')
    def test_generate_image_success(self, mock_append_log):
        # Mock the OpenAI API response
        mock_data_item = MagicMock()
        mock_data_item.url = "https://example.com/image.png"
        
        mock_response = MagicMock()
        mock_response.data = [mock_data_item]
        
        self.mock_client.images.generate.return_value = mock_response
        
        # Mock saving image
        with patch.object(self.img_gen, '_save_image_from_url', return_value='/path/to/saved/image.png') as mock_save:
            result = self.img_gen.generate_image("test prompt")
            
            # Assert OpenAI API was called correctly
            self.mock_client.images.generate.assert_called_once_with(
                model="dall-e-3",
                prompt="test prompt",
                size="1024x1024",
                quality="standard",
                n=1
            )
            
            # Check result structure
            self.assertTrue('url' in result)
            self.assertTrue('local_path' in result)
            self.assertTrue('relative_path' in result)
            self.assertEqual(result['url'], "https://example.com/image.png")

    @patch('model_api.img_gen.append_to_log')
    def test_generate_image_failure(self, mock_append_log):
        # Make the API call fail
        self.mock_client.images.generate.side_effect = Exception("API Error")
        
        result = self.img_gen.generate_image("test prompt")
        
        # Check error handling
        self.assertTrue('error' in result)
        self.assertEqual(result['error'], "API Error")

    @patch('model_api.img_gen.requests.get')
    @patch('model_api.img_gen.append_to_log')
    @patch('model_api.img_gen.Image.open')
    def test_save_image_from_url(self, mock_image_open, mock_append_log, mock_requests_get):
        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.content = b'fake image data'
        mock_requests_get.return_value = mock_response
        
        # Mock PIL image
        mock_img = MagicMock()
        mock_image_open.return_value = mock_img
        
        result = self.img_gen._save_image_from_url("https://example.com/image.png", "test.png")
        
        # Verify image was saved
        mock_img.save.assert_called_once()
        self.assertIsNotNone(result)
    
    @patch('model_api.img_gen.append_to_log')
    def test_enhance_prompt(self, mock_append_log):
        # Mock the OpenAI chat API response
        mock_choice = MagicMock()
        mock_choice.message.content = "Enhanced prompt text"
        
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        
        self.mock_client.chat.completions.create.return_value = mock_response
        
        result = self.img_gen.enhance_prompt("Basic prompt")
        
        # Assert that the chat API was called correctly
        self.mock_client.chat.completions.create.assert_called_once()
        self.assertEqual(result, "Enhanced prompt text")
    
    @patch('model_api.img_gen.append_to_log')
    def test_enhance_prompt_failure(self, mock_append_log):
        # Make the API call fail
        self.mock_client.chat.completions.create.side_effect = Exception("API Error")
        
        # Original prompt should be returned on failure
        result = self.img_gen.enhance_prompt("Basic prompt")
        self.assertEqual(result, "Basic prompt")

    @patch('model_api.img_gen.append_to_log')
    def test_generate_variation(self, mock_append_log):
        # Mock the OpenAI API response
        mock_data_item = MagicMock()
        mock_data_item.url = "https://example.com/variation.png"
        
        mock_response = MagicMock()
        mock_response.data = [mock_data_item]
        
        self.mock_client.images.create_variation.return_value = mock_response
        
        # Mock file operations
        mock_file = mock.mock_open(read_data=b'test image data')
        with patch('builtins.open', mock_file):
            # Mock saving image
            with patch.object(self.img_gen, '_save_image_from_url', return_value='/path/to/variation.png') as mock_save:
                result = self.img_gen.generate_variation("/path/to/image.png")
                
                # Assert API was called correctly
                self.mock_client.images.create_variation.assert_called_once()
                
                # Check result
                self.assertEqual(len(result), 1)
                self.assertEqual(result[0], '/path/to/variation.png')


if __name__ == '__main__':
    unittest.main()
