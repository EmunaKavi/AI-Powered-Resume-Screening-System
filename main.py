import re
import string
import numpy as np
from flask import Flask, request, jsonify, render_template, send_from_directory
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from collections import Counter
import PyPDF2
import docx
import io
import json
import os

app = Flask(__name__)

class ResumeScanner:
    def __init__(self):
        self.vectorizer = TfidfVectorizer(
            stop_words='english',
            lowercase=True,
            max_features=1000,
            ngram_range=(1, 2)
        )
        
        # Predefined skill categories
        self.skill_keywords = {
            'programming': [
                'python', 'java', 'javascript', 'c++', 'c#', 'php', 'ruby', 'go',
                'swift', 'kotlin', 'scala', 'r', 'matlab', 'sql', 'html', 'css',
                'typescript', 'dart', 'perl', 'bash', 'powershell'
            ],
            'frameworks': [
                'react', 'angular', 'vue', 'django', 'flask', 'spring', 'nodejs',
                'express', 'laravel', 'rails', 'asp.net', 'tensorflow', 'pytorch',
                'keras', 'fastapi', 'nextjs', 'nuxt', 'svelte', 'bootstrap'
            ],
            'databases': [
                'mysql', 'postgresql', 'mongodb', 'redis', 'elasticsearch',
                'oracle', 'sqlite', 'cassandra', 'dynamodb', 'firebase',
                'mariadb', 'neo4j', 'influxdb', 'couchdb'
            ],
            'cloud_tools': [
                'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'jenkins',
                'git', 'github', 'gitlab', 'bitbucket', 'terraform', 'ansible',
                'vagrant', 'circleci', 'travis', 'heroku', 'netlify'
            ],
            'operating_systems': [
                'linux', 'ubuntu', 'centos', 'redhat', 'windows', 'macos',
                'unix', 'debian', 'fedora', 'arch'
            ],
            'data_science': [
                'pandas', 'numpy', 'scikit-learn', 'matplotlib', 'seaborn',
                'plotly', 'jupyter', 'tableau', 'power bi', 'spark', 'hadoop',
                'kafka', 'airflow', 'mlflow'
            ],
            'soft_skills': [
                'leadership', 'communication', 'teamwork', 'problem solving',
                'analytical', 'creative', 'adaptable', 'organized', 'management',
                'collaboration', 'presentation', 'negotiation', 'mentoring'
            ]
        }
    
    def extract_text_from_pdf(self, file_content):
        """Extract text from PDF file"""
        try:
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            return text
        except Exception as e:
            return f"Error reading PDF: {str(e)}"
    
    def extract_text_from_docx(self, file_content):
        """Extract text from DOCX file"""
        try:
            doc = docx.Document(io.BytesIO(file_content))
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            return text
        except Exception as e:
            return f"Error reading DOCX: {str(e)}"
    
    def preprocess_text(self, text):
        """Clean and preprocess text"""
        # Convert to lowercase
        text = text.lower()
        
        # Remove special characters and extra whitespace
        text = re.sub(r'[^a-zA-Z0-9\s]', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
    
    def extract_skills(self, text):
        """Extract skills from resume text"""
        text = self.preprocess_text(text)
        found_skills = {}
        
        for category, skills in self.skill_keywords.items():
            found_skills[category] = []
            for skill in skills:
                if skill.lower() in text:
                    found_skills[category].append(skill)
        
        return found_skills
    
    def extract_contact_info(self, text):
        """Extract contact information from resume"""
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        phone_pattern = r'(\+\d{1,3}[-.\s]?)?\(?(\d{3})\)?[-.\s]?(\d{3})[-.\s]?(\d{4})'
        
        emails = re.findall(email_pattern, text)
        phones = re.findall(phone_pattern, text)
        
        return {
            'emails': emails,
            'phones': [''.join(phone) for phone in phones]
        }
    
    def extract_experience(self, text):
        """Extract years of experience from resume"""
        experience_patterns = [
            r'(\d+)\+?\s*years?\s*(?:of\s*)?experience',
            r'experience\s*[:.]?\s*(\d+)\+?\s*years?',
            r'(\d+)\+?\s*yrs?\s*(?:of\s*)?experience',
        ]
        
        years = []
        for pattern in experience_patterns:
            matches = re.findall(pattern, text.lower())
            years.extend([int(match) for match in matches])
        
        return max(years) if years else 0
    
    def calculate_similarity(self, resume_text, job_description):
        """Calculate similarity between resume and job description using TF-IDF and cosine similarity"""
        documents = [self.preprocess_text(resume_text), self.preprocess_text(job_description)]
        
        try:
            tfidf_matrix = self.vectorizer.fit_transform(documents)
            similarity_score = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            return similarity_score
        except Exception as e:
            return 0.0
    
    def rank_candidates(self, candidates, job_description):
        """Rank candidates based on their similarity to job description"""
        ranked_candidates = []
        
        for candidate in candidates:
            similarity_score = self.calculate_similarity(candidate['resume_text'], job_description)
            candidate['similarity_score'] = similarity_score
            candidate['percentage_match'] = round(similarity_score * 100, 2)
            ranked_candidates.append(candidate)
        
        # Sort by similarity score in descending order
        ranked_candidates.sort(key=lambda x: x['similarity_score'], reverse=True)
        
        return ranked_candidates

# Initialize the scanner
scanner = ResumeScanner()

@app.route('/')
def index():
    """Serve the main HTML page"""
    return render_template('index.html')

@app.route('/static/<path:filename>')
def static_files(filename):
    """Serve static files"""
    return send_from_directory('static', filename)

@app.route('/scan', methods=['POST'])
def scan_resumes():
    """Main endpoint for scanning and ranking resumes"""
    try:
        job_description = request.form.get('job_description', '')
        if not job_description:
            return jsonify({'error': 'Job description is required'})
        
        files = request.files.getlist('resumes')
        if not files:
            return jsonify({'error': 'No resume files uploaded'})
        
        candidates = []
        processed_files = 0
        
        for file in files:
            if file.filename == '':
                continue
                
            file_content = file.read()
            filename = file.filename
            
            # Extract text based on file type
            if filename.lower().endswith('.pdf'):
                resume_text = scanner.extract_text_from_pdf(file_content)
            elif filename.lower().endswith('.docx'):
                resume_text = scanner.extract_text_from_docx(file_content)
            else:
                continue  # Skip unsupported file types
            
            if resume_text and not resume_text.startswith('Error'):
                # Extract skills, contact info, and experience
                skills = scanner.extract_skills(resume_text)
                contact_info = scanner.extract_contact_info(resume_text)
                experience_years = scanner.extract_experience(resume_text)
                
                candidate = {
                    'filename': filename,
                    'resume_text': resume_text,
                    'skills': skills,
                    'contact_info': contact_info,
                    'experience_years': experience_years
                }
                candidates.append(candidate)
                processed_files += 1
        
        if not candidates:
            return jsonify({'error': 'No valid resumes could be processed'})
        
        # Rank candidates
        ranked_candidates = scanner.rank_candidates(candidates, job_description)
        
        # Remove resume_text from response to reduce size
        for candidate in ranked_candidates:
            del candidate['resume_text']
        
        return jsonify({
            'ranked_candidates': ranked_candidates,
            'total_candidates': len(ranked_candidates),
            'processed_files': processed_files,
            'success': True
        })
        
    except Exception as e:
        return jsonify({'error': str(e), 'success': False})

@app.route('/api/analyze', methods=['POST'])
def api_analyze():
    """API endpoint for programmatic access"""
    try:
        data = request.json
        job_description = data.get('job_description', '')
        resume_text = data.get('resume_text', '')
        
        if not job_description or not resume_text:
            return jsonify({'error': 'Both job_description and resume_text are required'})
        
        # Analyze single resume
        skills = scanner.extract_skills(resume_text)
        contact_info = scanner.extract_contact_info(resume_text)
        experience_years = scanner.extract_experience(resume_text)
        similarity_score = scanner.calculate_similarity(resume_text, job_description)
        
        return jsonify({
            'similarity_score': similarity_score,
            'percentage_match': round(similarity_score * 100, 2),
            'skills': skills,
            'contact_info': contact_info,
            'experience_years': experience_years,
            'success': True
        })
        
    except Exception as e:
        return jsonify({'error': str(e), 'success': False})

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'AI Resume Scanner',
        'version': '1.0.0'
    })

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    if not os.path.exists('templates'):
        os.makedirs('templates')
    
    # Create static directory if it doesn't exist
    if not os.path.exists('static'):
        os.makedirs('static')
    
    print("🚀 Starting AI-Powered Resume Scanner...")
    print("📊 Features:")
    print("   - PDF and DOCX resume parsing")
    print("   - TF-IDF and Cosine Similarity matching")
    print("   - Advanced skill extraction and categorization")
    print("   - Contact information and experience extraction")
    print("   - Intelligent candidate ranking and scoring")
    print("   - Professional web interface")
    print("\n🌐 Access the web interface at: http://localhost:5000")
    print("🔗 API endpoint available at: http://localhost:5000/api/analyze")
    print("💊 Health check at: http://localhost:5000/health")
    
    app.run(debug=True, host='0.0.0.0', port=5000)