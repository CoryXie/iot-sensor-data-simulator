from sqlalchemy import Column, Integer, String
from src.models.base_model import BaseModel

class Options(BaseModel):
    """System configuration options"""
    __tablename__ = 'options'
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)
    value = Column(String(200))
    description = Column(String(200))
    
    def __init__(self, name: str, value: str, description: str = None):
        self.name = name
        self.value = value
        self.description = description

    def __repr__(self):
        return f"<Option(name='{self.name}', value='{self.value}')>" 