import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import climate, select
from esphome.components.logger import HARDWARE_UART_TO_SERIAL
from esphome.const import (
    CONF_ID,
    CONF_HARDWARE_UART,
    CONF_BAUD_RATE,
    CONF_UPDATE_INTERVAL,
    CONF_MODE,
    CONF_FAN_MODE,
    CONF_SWING_MODE,
)
from esphome.core import CORE, coroutine

AUTO_LOAD = ["climate", "select"]

CONF_SUPPORTS = "supports"
CONF_HORIZONTAL_VANE_SELECT = "horizontal_vane_select"
CONF_VERTICAL_VANE_SELECT = "vertical_vane_select"
DEFAULT_CLIMATE_MODES = ["HEAT_COOL", "COOL", "HEAT", "DRY", "FAN_ONLY"]
DEFAULT_FAN_MODES = ["AUTO", "DIFFUSE", "LOW", "MEDIUM", "MIDDLE", "HIGH"]
DEFAULT_SWING_MODES = ["OFF", "VERTICAL", "HORIZONTAL", "BOTH"]
DEFAULT_HORIZONTAL_VANE_OPTIONS = ["SWING", "LEFT", "LEFT_CENTER", "CENTER", "RIGHT_CENTER", "RIGHT"]
DEFAULT_VERTICAL_VANE_OPTIONS = ["SWING", "AUTO", "UP", "UP_CENTER", "CENTER", "DOWN_CENTER", "DOWN"]

MitsubishiHeatPump = cg.global_ns.class_(
    "MitsubishiHeatPump", climate.Climate, cg.PollingComponent
)

MitsubishiACSelect = cg.global_ns.class_(
    "MitsubishiACSelect", select.Select, cg.Component
)

def valid_uart(uart):
    if CORE.is_esp8266:
        uarts = ["UART0"]  # UART1 is tx-only
    elif CORE.is_esp32:
        uarts = ["UART0", "UART1", "UART2"]
    else:
        raise NotImplementedError

    return cv.one_of(*uarts, upper=True)(uart)


SELECT_SCHEMA = select.SELECT_SCHEMA.extend(
    {
        cv.GenerateID(CONF_ID): cv.declare_id(MitsubishiACSelect)
    }
)

CONFIG_SCHEMA = climate.CLIMATE_SCHEMA.extend(
    {
        cv.GenerateID(): cv.declare_id(MitsubishiHeatPump),
        cv.Optional(CONF_HARDWARE_UART, default="UART0"): valid_uart,
        cv.Optional(CONF_BAUD_RATE): cv.positive_int,
        # If polling interval is greater than 9 seconds, the HeatPump library
        # reconnects, but doesn't then follow up with our data request.
        cv.Optional(CONF_UPDATE_INTERVAL, default="500ms"): cv.All(
            cv.update_interval, cv.Range(max=cv.TimePeriod(milliseconds=9000))
        ),
        # Add selects for vertical and horizontal vane positions
        cv.Optional(CONF_HORIZONTAL_VANE_SELECT): SELECT_SCHEMA,
        cv.Optional(CONF_VERTICAL_VANE_SELECT): SELECT_SCHEMA,
        # Optionally override the supported ClimateTraits.
        cv.Optional(CONF_SUPPORTS, default={}): cv.Schema(
            {
                cv.Optional(CONF_MODE, default=DEFAULT_CLIMATE_MODES):
                    cv.ensure_list(climate.validate_climate_mode),
                cv.Optional(CONF_FAN_MODE, default=DEFAULT_FAN_MODES):
                    cv.ensure_list(climate.validate_climate_fan_mode),
                cv.Optional(CONF_SWING_MODE, default=DEFAULT_SWING_MODES):
                    cv.ensure_list(climate.validate_climate_swing_mode),
            }
        ),
    }
).extend(cv.COMPONENT_SCHEMA)


@coroutine
def to_code(config):
    serial = HARDWARE_UART_TO_SERIAL[config[CONF_HARDWARE_UART]]
    var = cg.new_Pvariable(config[CONF_ID], cg.RawExpression(f"&{serial}"))

    if CONF_BAUD_RATE in config:
        cg.add(var.set_baud_rate(config[CONF_BAUD_RATE]))

    supports = config[CONF_SUPPORTS]
    traits = var.config_traits()

    for mode in supports[CONF_MODE]:
        if mode == "OFF":
            continue
        cg.add(traits.add_supported_mode(climate.CLIMATE_MODES[mode]))

    for mode in supports[CONF_FAN_MODE]:
        cg.add(traits.add_supported_fan_mode(climate.CLIMATE_FAN_MODES[mode]))

    for mode in supports[CONF_SWING_MODE]:
        cg.add(traits.add_supported_swing_mode(climate.CLIMATE_SWING_MODES[mode]))

    if CONF_HORIZONTAL_VANE_SELECT in config:
        conf = config[CONF_HORIZONTAL_VANE_SELECT]
        vane_select = yield select.new_select(conf, options=DEFAULT_HORIZONTAL_VANE_OPTIONS)
        yield cg.register_component(vane_select, conf)
        cg.add(var.set_horizontal_vane_select(vane_select))

    if CONF_VERTICAL_VANE_SELECT in config:
        conf = config[CONF_VERTICAL_VANE_SELECT]
        vane_select = yield select.new_select(conf, options=DEFAULT_VERTICAL_VANE_OPTIONS)
        yield cg.register_component(vane_select, conf)
        cg.add(var.set_vertical_vane_select(vane_select))

    yield cg.register_component(var, config)
    yield climate.register_climate(var, config)
    cg.add_library(
        name="HeatPump",
        repository="https://github.com/SwiCago/HeatPump",
        version="d6a29134401d7caae1b8fca9c452c8eb92af60c5",
    )
