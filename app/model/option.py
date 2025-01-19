from model.models import OptionModel
from loguru import logger


class Option(OptionModel):
    '''This class represents an option. Options are used to store global settings.'''

    @staticmethod
    def _get_option(name):
        '''Returns the option with the given name'''
        option = Option.session.query(OptionModel).filter_by(name=name).first()
        logger.debug(f"Retrieved option '{name}': {option.value if option else 'not found'}")
        return option
    
    @staticmethod
    def get_value(name):
        '''Returns the value of the option with the given name'''
        option = Option._get_option(name)
        value = option.value if option is not None else None
        logger.debug(f"Retrieved value for option '{name}': {value}")
        return value
    
    @staticmethod
    def get_boolean(name):
        '''Returns the boolean value of the option with the given name'''
        value = Option.get_value(name)
        if value is None:
            logger.debug(f"Option '{name}' not found, returning False")
            return False
        result = value == "1"
        logger.debug(f"Retrieved boolean value for option '{name}': {result}")
        return result

    @staticmethod
    def set_value(name, value):
        '''Sets value of existing option or creates a new option with the given name'''
        logger.info(f"Setting option '{name}' to value: {value}")
        try:
            option = Option._get_option(name)
            if option is None:
                option = Option(name=name, value=value)
                Option.session.add(option)
                logger.debug(f"Created new option '{name}'")
            else:
                option.value = value
                logger.debug(f"Updated existing option '{name}'")
            Option.session.commit()
            logger.info(f"Successfully set option '{name}' to value: {value}")
            return option
        except Exception as e:
            logger.exception(f"Error setting option '{name}': {str(e)}")
            raise
    

