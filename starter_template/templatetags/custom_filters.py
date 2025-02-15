from django import template
import re

register = template.Library()

@register.filter(name='convert_markup')
def convert_markup(text):
    if not text:
        return ""
    
    # Convert Markdown headers
    # text = re.sub(r'### (.*?)\n', r'<h3>\1</h3>', text)
    
    # Convert bold text
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
    
    # Convert bullet points
    text = re.sub(r'\n- (.*?)(?=\n|$)', r'<li>\1</li>', text)
    
    # Wrap bullet points in ul
    text = re.sub(r'(<li>.*?</li>)+', r'<ul>\g<0></ul>', text, flags=re.DOTALL)
    
    # Convert newlines to <br> tags
    text = text.replace('\n\n', '<br><br>')
    
    return text