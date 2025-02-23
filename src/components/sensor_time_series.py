from nicegui import ui
from loguru import logger
from datetime import datetime, timedelta
import plotly.graph_objects as go
from collections import deque
from typing import Dict, List, Any

class SensorTimeSeries:
    """Component for displaying sensor time series data"""
    
    def __init__(self, max_points: int = 100):
        """Initialize the time series component"""
        self.max_points = max_points
        self.times = deque(maxlen=max_points)
        self.values = deque(maxlen=max_points)
        self.status_markers: List[Dict] = []  # List to store status change markers
        
    def add_point(self, value: float, timestamp: datetime = None):
        """Add a new data point to the time series"""
        if timestamp is None:
            timestamp = datetime.now()
        self.times.append(timestamp)
        self.values.append(value)
        
    def add_status_marker(self, status: str, timestamp: datetime = None):
        """Add a status marker (e.g., 'stopped', 'started') at a specific time"""
        if timestamp is None:
            timestamp = datetime.now()
        self.status_markers.append({
            'time': timestamp,
            'status': status
        })
        
    def create_plot(self, sensor_type: str, unit: str) -> Any:
        """Create a plotly figure based on sensor type"""
        try:
            # Create the main line trace
            trace = go.Scatter(
                x=list(self.times),
                y=list(self.values),
                mode='lines',
                name='Value',
                line=dict(
                    color='#2196F3',
                    width=2
                )
            )
            
            # Create marker traces for status changes
            marker_traces = []
            for marker in self.status_markers:
                marker_traces.append(
                    go.Scatter(
                        x=[marker['time']],
                        y=[self.get_y_value_at_time(marker['time'])],
                        mode='markers+text',
                        name=marker['status'],
                        text=[marker['status']],
                        textposition="top center",
                        marker=dict(
                            symbol='star',
                            size=12,
                            color='red' if marker['status'].lower() == 'stopped' else 'green'
                        )
                    )
                )
            
            # Customize layout based on sensor type
            layout = go.Layout(
                title=f'Sensor Values Over Time',
                xaxis=dict(
                    title='Time',
                    showgrid=True,
                    gridcolor='rgba(128, 128, 128, 0.2)',
                ),
                yaxis=dict(
                    title=f'Value ({unit})',
                    showgrid=True,
                    gridcolor='rgba(128, 128, 128, 0.2)',
                ),
                plot_bgcolor='rgba(0, 0, 0, 0)',
                paper_bgcolor='rgba(0, 0, 0, 0)',
                margin=dict(l=50, r=50, t=50, b=50),
                showlegend=True,
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                )
            )
            
            # Add specific customizations based on sensor type
            if sensor_type.lower() == 'binary':
                layout.update(
                    yaxis=dict(
                        tickmode='array',
                        ticktext=['Off', 'On'],
                        tickvals=[0, 1],
                        range=[-0.2, 1.2]
                    )
                )
            elif sensor_type.lower() == 'categorical':
                layout.update(
                    yaxis=dict(
                        tickmode='array',
                        ticktext=list(set(self.values)),  # Unique categories
                        tickvals=list(range(len(set(self.values))))
                    )
                )
                
            fig = go.Figure(data=[trace] + marker_traces, layout=layout)
            return ui.plotly(fig).classes('w-full h-64')
            
        except Exception as e:
            logger.error(f"Error creating time series plot: {str(e)}")
            return ui.label("Error creating plot").classes('text-red-500')
            
    def get_y_value_at_time(self, target_time: datetime) -> float:
        """Get the sensor value at a specific time"""
        # Find the closest time point
        if not self.times:
            return 0
            
        closest_time_idx = min(range(len(self.times)), 
                             key=lambda i: abs(self.times[i] - target_time))
        return self.values[closest_time_idx]
