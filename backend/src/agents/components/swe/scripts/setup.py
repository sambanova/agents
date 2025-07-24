#!/usr/bin/env python3
import os
from pathlib import Path

def generate_env_example():
    project_root = Path(__file__).parent.parent
    source_env_file = project_root / '.env'
    target_env_example = project_root / '.env.example'
    
    if not source_env_file.exists():
        print(".env file not found!")
        return
    
    with open(source_env_file, 'r') as env_source:
        env_lines = env_source.readlines()
        
    processed_env_lines = []
    for line in env_lines:
        line = line.strip()
        # Keep comments and empty lines as is
        if not line or line.startswith('#'):
            processed_env_lines.append(line)
            continue
            
        # Replace values with placeholders
        if '=' in line:
            env_key = line.split('=')[0].strip()
            placeholder = ""
            processed_env_lines.append(f'{env_key}={placeholder}')
    
    with open(target_env_example, 'w') as env_target:
        env_target.write('\n'.join(processed_env_lines) + '\n')
    
    print('.env.example generated successfully!')

def copy_requirements():
    project_root = Path(__file__).parent.parent
    pipfile_path = project_root / 'Pipfile'
    target_requirements = project_root / 'requirements.txt'

    if not pipfile_path.exists():
        print('Pipfile not found in project root!')
        return

    # Use pipenv to generate requirements.txt
    result = os.system('pipenv requirements > requirements.txt')
    if result == 0:
        print('Requirements generated from Pipfile successfully!')
    else:
        print('Failed to generate requirements.txt from Pipfile!')

def setup():
    generate_env_example()
    # copy_requirements()

if __name__ == '__main__':
    setup() 