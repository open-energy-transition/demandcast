"""
Serve an XGBoost model for electricity demand prediction using FastAPI.

This module provides a REST API service to serve predictions from
a pre-trained XGBoost model.

It includes endpoints for health checks, model information,
and making predictions based on passed features.
"""

import argparse
import sys
from typing import Optional

import inference
import pandas
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


class PredictionInput(BaseModel):
    """Define input data for prediction."""

    is_weekend: int = Field(ge=0, le=1)
    hour: int = Field(ge=0, lt=24)
    month: int = Field(ge=1, le=12)
    month_temp_avg: float
    month_temp_rank: int = Field(ge=1, le=12)
    year_electricity_demand_per_capita: float
    year_gdp_ppp: float = Field(gt=0)
    year_temp_percentile_5: float
    year_temp_percentile_95: float
    year_temp_top3: float


class PredictionOutput(BaseModel):
    """Define output data for prediction."""

    prediction: float
    timestamp: Optional[str] = None


def setupFastAPI(args: argparse.Namespace):
    """
    Set up FastAPI app with specified command line arguments.

    Parameters
    ----------
    args : argparse.Namespace
        Arguments from the command line.

    Returns
    -------
    app : FastAPI
        Initialized FastAPI app
    """
    app = FastAPI(
        title="Electricity Demand Prediction API",
        description="API for predicting electricity demand using XGBoost model",
    )

    # Load the model at startup
    @app.on_event("startup")
    async def load_model():
        """Load the XGBoost model at startup."""
        global model
        try:
            app.state.model = inference.load_model(args.model_location)
        except Exception as e:
            print(f"Unexpected error loading model: {e}")
            app.state.model = None
            sys.exit(1)

    @app.get("/")
    def read_root():
        """
        Get general information about the service.

        Returns
        -------
        dict:
            service: str
                Name of the service
            status: str
                Status of the service
            model: str
                Name of the model used for prediction
            endpoints: dict
                Description of available endpoints
        """
        return {
            "service": "DemandCast API",
            "status": "active",
            "model": "XGBoost",
            "endpoints": {
                "/predict": "Make predictions using the model",
                "/health": "Check the health of the service",
            },
        }

    @app.get("/health")
    def health_check():
        """
        Check whether the model is loaded.

        Returns
        -------
        dict:
            status: str
                "healthy" if the model is loaded, otherwise "unhealthy"
            model_loaded: bool
                True if the model is loaded, otherwise False
        """
        if app.state.model is not None:
            return {"status": "healthy", "model_loaded": True}
        return {"status": "unhealthy", "model_loaded": False}

    @app.post("/predict", response_model=PredictionOutput)
    def predict(input_data: PredictionInput):
        """
        Predict normalized electricity demand with required freatures.

        Parameters
        ----------
        input_data : PredictionInput
            See class PredictionInput for details

        Returns
        -------
        PredictionOutput:
            See class PredictionOutput for details
            prediction: float
                The predicted normalized electricity demand
            timestamp: str
                The timestamp of the prediction

        Raises
        ------
        HTTPException
            Catches all errors, such as if prediction fails
        """
        if app.state.model is None:
            raise HTTPException(status_code=503, detail="Model not loaded")

        try:
            # Convert input features to DataFrame
            df_features = pandas.DataFrame.from_dict([input_data.model_dump()])

            # Make prediction
            prediction = app.state.model.predict(df_features)

            # Return prediction
            return PredictionOutput(
                prediction=prediction,
                timestamp=pandas.Timestamp.now().isoformat(),
            )
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Prediction error: {str(e)}"
            )

    return app


def read_command_line_arguments() -> argparse.Namespace:
    """
    Create a parser for the command line arguments.

    Returns
    -------
    args : argparse.Namespace
        The parsed command line arguments.
    """
    parser = argparse.ArgumentParser(description="")

    parser.add_argument(
        "-ml",
        "--model_location",
        type=str,
        default="inference/xgboost_model.bin",
        help='Location of the XGBoost model file (default: "inference/xgboost_model.bin")',
        required=False,
    )

    # Read the arguments from the command line.
    args = parser.parse_args()

    return args


if __name__ == "__main__":
    """Serve the XGBoost model using FastAPI"""

    # Read command line arguments
    args = read_command_line_arguments()

    #  Initialize the FastAPI app
    app = setupFastAPI(args)

    uvicorn.run(app, host="0.0.0.0", port=8000)
