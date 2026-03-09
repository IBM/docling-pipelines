from collections import defaultdict

from common.models.session_info import get_session_info
from common.util.log import get_logger
from core.orchestrator.operator_factory import OperatorFactoryProvider
from common.util.constants import OrchestratorType, OperatorConstants

logger = get_logger()


class OperatorMetadata:
    def __init__(self):
        self.session_info = get_session_info()
        self.operator_metadata = {}

    def get_operator_metadata(self, *, internal_features=False):
        refresh_operator_metadata = {}
        config = {}
        failed_operator_list = {}
        operator_factory = OperatorFactoryProvider.get_operator_factory(
            orchestrator=OrchestratorType.PYTHON
        )
        logger.info(f"Available Operators: {operator_factory.operators.keys()}")
        for short_name, cls in operator_factory.operators.items():
            try:
                op = cls(config)
                config_values = op.get_metadata()
                required_features = op.get_required_features()
                config_values["required_features"] = required_features
                if not internal_features:
                    features = config_values.get(OperatorConstants.FEATURES, {})
                    filtered_features = {
                        k: v
                        for k, v in features.items()
                        if OperatorConstants.INTERNAL_FEATURE
                        not in v.get(OperatorConstants.TAGS, [])
                    }
                    config_values[OperatorConstants.FEATURES] = filtered_features

                refresh_operator_metadata[short_name] = config_values
            except Exception as e:
                refresh_operator_metadata[short_name] = {}
                failed_operator_list[short_name] = e
                continue
        self.operator_metadata.update(refresh_operator_metadata)

        if len(failed_operator_list) > 0:
            # Below dict would be used for metadata missing log.
            updated_operator_list = {}

            for op_name, exception in failed_operator_list.items():
                operator = operator_factory.get_operator(operator_name=op_name)
                if operator.is_available():
                    updated_operator_list[op_name] = exception

            logger.warning(f"Metadata missing for {updated_operator_list}")

        return self.operator_metadata

    def get_features(self, *, short_name: str, purpose: str = None) -> dict:
        """
        Returns the features from the given operator for the purpose of
         a) filtering (OperatorConstants.AVAILABLE_FOR_FILTER) or b) Vector DB (OperatorConstants.AVAILABLE_FOR_VECTOR_DB)`
        """
        if (
            self.operator_metadata.get(short_name) is not None
            and self.operator_metadata.get(short_name).get(OperatorConstants.FEATURES)
            is not None
        ):
            features: dict = self.operator_metadata.get(short_name).get(
                OperatorConstants.FEATURES
            )
            if purpose is None:
                return {k: v for k, v in features.items()}
            else:
                return {k: v for k, v in features.items() if v.get(purpose, False)}
        else:
            return {}

    def get_features_from_input_output_features(
        self,
        *,
        purpose: str = None,
        input_features: dict = None,
        output_features: dict = None,
    ) -> dict:
        """
        Returns the features from the given operator for the purpose of
         a) filtering (OperatorConstants.AVAILABLE_FOR_FILTER) or b) Vector DB (OperatorConstants.AVAILABLE_FOR_VECTOR_DB)`
        """
        features: dict = {}
        if input_features:
            features = input_features.copy()
        if output_features:
            features.update(output_features)
        if len(features) > 0:
            if purpose is None:
                return {k: v for k, v in features.items()}
            else:
                return {k: v for k, v in features.items() if v.get(purpose, False)}
        else:
            return features

    def required_feature_names(self, *, short_name):
        return self.operator_metadata.get(short_name, {}).get("required_features", [])

    def get_feature_operators_map(self):
        _ = self.get_operator_metadata(internal_features=True)
        operator_short_names = list(self.operator_metadata.keys())
        feature_operators_map = defaultdict(list)
        for short_name in operator_short_names:
            op_features = list(self.get_features(short_name=short_name).keys())
            for feature in op_features:
                label = self.operator_metadata.get(short_name).get(
                    OperatorConstants.LABEL, None
                )
                if label:
                    feature_operators_map[feature].append(label)

        return feature_operators_map


# Only used for unit testing
def main():  # pragma: no cover

    operator = OperatorMetadata()
    operator_items = operator.get_operator_metadata()
    for key, value in operator_items.items():
        print(f"Key: {key}, value: {value}")


if __name__ == "__main__":  # pragma: no cover
    main()
