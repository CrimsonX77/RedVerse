# Contributing to RedVerse

Thank you for your interest in contributing to The RedVerse! This document provides guidelines for contributing to the project.

## 🎯 Ways to Contribute

- **Bug Reports**: Submit detailed bug reports with reproduction steps
- **Feature Requests**: Suggest new features or enhancements
- **Code Contributions**: Submit pull requests for bug fixes or new features
- **Documentation**: Improve README, setup guides, or code comments
- **Testing**: Test on different platforms and report issues
- **Design**: Contribute to UI/UX improvements

## 📋 Before You Start

1. Check existing issues to avoid duplicates
2. For major changes, open an issue first to discuss
3. Follow the existing code style and conventions
4. Test your changes thoroughly

## 🔧 Development Setup

```bash
# Fork and clone your fork
git clone https://github.com/Crimsonx77/Redverse.git
cd Redverse

# Set up development environment
pyenv virtualenv 3.10.16 redverse-dev
pyenv activate redverse-dev
pip install -r requirements.txt

# Create a branch for your changes
git checkout -b feature/your-feature-name
```

## 📝 Coding Standards

### Python
- Follow PEP 8 style guide
- Use descriptive variable names
- Add docstrings to functions and classes
- Keep functions focused and modular
- Use type hints where appropriate

### HTML/CSS
- Maintain consistent indentation (2 spaces)
- Use semantic HTML elements
- Follow existing naming conventions
- Comment complex CSS rules

### YAML Configurations
- Maintain consistent structure
- Document custom fields
- Follow existing templates in `pads/`

## 🧪 Testing

Before submitting:
- Test all modified Python tools
- Verify HTML pages render correctly
- Check cross-browser compatibility for web components
- Ensure no hardcoded paths or credentials

## 📤 Submitting Changes

### Pull Request Process

1. **Update your branch**
   ```bash
   git fetch origin
   git rebase origin/main
   ```

2. **Commit your changes**
   ```bash
   git add .
   git commit -m "Clear description of changes"
   ```
   
   **Commit Message Format:**
   ```
   category: brief description
   
   Detailed explanation if needed.
   
   Fixes #issue_number (if applicable)
   ```
   
   Examples:
   - `feat: add new emotion visualization mode`
   - `fix: resolve path issue in dragon_forge.sh`
   - `docs: update installation instructions`
   - `style: improve responsive design for mobile`

3. **Push to your fork**
   ```bash
   git push origin feature/your-feature-name
   ```

4. **Open a Pull Request**
   - Use a clear, descriptive title
   - Reference related issues
   - Describe what changed and why
   - Include screenshots for UI changes
   - List any breaking changes

### PR Checklist

- [ ] Code follows project style guidelines
- [ ] Comments added for complex logic
- [ ] Documentation updated if needed
- [ ] No hardcoded credentials or paths
- [ ] Tested on local environment
- [ ] No merge conflicts with main branch
- [ ] `.gitignore` properly excludes sensitive files

## 🏗️ Project Structure

```
Key areas for contribution:

- Python tools: Core functionality improvements
- Web interface: UI/UX enhancements, responsiveness
- Soul system: New character templates, scenarios
- Documentation: Setup guides, tutorials
- Themes: New visual themes and styles
```

## 🐛 Bug Reports

**Good bug reports include:**
- Clear, descriptive title
- Steps to reproduce
- Expected behavior
- Actual behavior
- System information (OS, Python version)
- Screenshots or error logs
- Relevant configuration files (without sensitive data)

**Template:**
```markdown
**Description**
[Clear description of the bug]

**To Reproduce**
1. Go to...
2. Click on...
3. See error...

**Expected Behavior**
[What should happen]

**Actual Behavior**
[What actually happens]

**Environment**
- OS: [e.g., Ubuntu 22.04]
- Python: [e.g., 3.10.16]
- Browser: [if web-related]

**Additional Context**
[Any other relevant information]
```

## 💡 Feature Requests

**Good feature requests include:**
- Clear use case
- Proposed solution or approach
- Alternative solutions considered
- Why this benefits the project
- Mockups or examples (if applicable)

## 🔒 Security

**Do NOT:**
- Commit API keys, credentials, or tokens
- Include personal data in examples
- Push the `Sables_Room/` directory
- Hardcode absolute paths in shared code

**If you find a security issue:**
- Do NOT open a public issue
- Email the maintainer directly
- Provide details and potential impact

## 📚 Documentation

When contributing documentation:
- Use clear, concise language
- Include code examples
- Add screenshots where helpful
- Test all commands/instructions
- Update table of contents if needed

## 🎨 Design Contributions

For UI/UX improvements:
- Maintain the Crimson Cathedral aesthetic
- Follow existing color schemes
- Ensure accessibility (contrast, screen readers)
- Test responsive design
- Provide before/after screenshots

## 🌟 Recognition

Contributors will be:
- Listed in a CONTRIBUTORS.md file
- Credited in release notes
- Acknowledged in the project community

## 📞 Questions?

- Open a discussion on GitHub
- Check existing documentation
- Review closed issues for similar questions

## 📜 License

By contributing, you agree that your contributions will be licensed under the same license as the project.

---

**Thank you for contributing to The RedVerse! 🔴**
