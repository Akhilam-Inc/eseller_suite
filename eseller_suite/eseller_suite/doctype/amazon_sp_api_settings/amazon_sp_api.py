# Copyright (c) 2024, efeone and contributors
# For license information, please see license.txt

from requests import request
import urllib.parse
import frappe

__all__ = [
	"SPAPIError",
	"Finances",
	"Orders",
	"CatalogItems",
]


# https://github.com/amzn/selling-partner-api-docs/blob/main/guides/en-US/developer-guide/SellingPartnerApiDeveloperGuide.md#selling-partner-api-endpoints
MARKETPLACES = {
	"North America": {
		"CA": "A2EUQ1WTGCTBG2",
		"US": "ATVPDKIKX0DER",
		"MX": "A1AM78C64UM0Y8",
		"BR": "A2Q3Y263D00KWC",
		"AWS Region": "us-east-1",
		"Endpoint": "https://sellingpartnerapi-na.amazon.com",
	},
	"Europe": {
		"ES": "A1RKKUPIHCS9HS",
		"GB": "A1F83G8C2ARO7P",
		"FR": "A13V1IB3VIYZZH",
		"NL": "A1805IZSGTT6HS",
		"DE": "A1PA6795UKMFR9",
		"IT": "APJ6JRA9NG5V4",
		"SE": "A2NODRKZP88ZB9",
		"PL": "A1C3SOZRARQ6R3",
		"EG": "ARBP9OOSHTCHU",
		"TR": "A33AVAJ2PDY3EV",
		"SA": "A17E79C6D8DWNP",
		"AE": "A2VIGQ35RCS4UG",
		"IN": "A21TJRUUN4KGV",
		"AWS Region": "eu-west-1",
		"Endpoint": "https://sellingpartnerapi-eu.amazon.com",
	},
	"Far East": {
		"SG": "A19VAU5U5O7RUS",
		"AU": "A39IBJ37TRP1C6",
		"JP": "A1VC38T7YXB528",
		"AWS Region": "us-west-2",
		"Endpoint": "https://sellingpartnerapi-fe.amazon.com",
	},
}

# Following code is adapted from https://github.com/andrewjroth/requests-auth-aws-sigv4 under the Apache License 2.0 with minor changes.

# Copyright 2020 Andrew J Roth <andrew@andrewjroth.com>

# Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

# 1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.

# 2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.

# 3. Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.

class SPAPIError(Exception):
	"""
	Main SP-API Exception class
	"""

	def __init__(self, *args, **kwargs) -> None:
		self.error = kwargs.get("error", "-")
		self.error_description = kwargs.get("error_description", "-")
		super().__init__(*args)

class SPAPI(object):
	""" Base Amazon SP-API class """

	# https://github.com/amzn/selling-partner-api-docs/blob/main/guides/en-US/developer-guide/SellingPartnerApiDeveloperGuide.md#connecting-to-the-selling-partner-api
	AUTH_URL = "https://api.amazon.com/auth/o2/token"

	BASE_URI = "/"

	def __init__(
		self,
		client_id: str,
		client_secret: str,
		refresh_token: str,
		country_code: str = "IN",
	) -> None:
		self.client_id = client_id
		self.client_secret = client_secret
		self.refresh_token = refresh_token
		self.country_code = country_code
		self.region, self.endpoint, self.marketplace_id = Util.get_marketplace_data(country_code)
		# Store last request/response details for logging
		self.last_request_details = None
		
	def get_access_token(self) -> str:
		client_id = (self.client_id or "").strip()
		client_secret = (self.client_secret or "").strip()
		refresh_token = (self.refresh_token or "").strip()
		data = {
			"grant_type": "refresh_token",
			"client_id": self.client_id,
			"client_secret": self.client_secret,
			"refresh_token": self.refresh_token,
		}

		headers = {
			"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"
		}

		# Use urlencode (percent-encodes reserved chars). This is fine in most cases.
		encoded_body = urllib.parse.urlencode(data)

		response = request(method="POST", url=self.AUTH_URL, data=encoded_body, headers=headers)

		# Debug log to confirm what was actually sent (useful if still failing)
		try:
			sent_body = getattr(response.request, "body", None) or getattr(response.request, "data", None)
			sent_headers = getattr(response.request, "headers", None)
		except Exception:
			sent_body, sent_headers = None, None

		frappe.log_error(
			title="Amazon Token Debug",
			message=f"Sent headers: {sent_headers}\nSent body: {sent_body}\nResp status: {response.status_code}\nResp body: {response.text}"
		)

		result = response.json()
		if response.status_code == 200:
			frappe.log_error(title="Amazon SP Token", message=f"{result}")
			return result.get("access_token")

		exception = SPAPIError(error=result.get("error"), error_description=result.get("error_description"))
		raise exception
	# def get_access_token(self) -> str:
	# 	data = {
	# 		"grant_type": "refresh_token",
	# 		"client_id": self.client_id,
	# 		"client_secret": self.client_secret,
	# 		"refresh_token": self.refresh_token,
	# 	}

	# 	headers = {
	# 		'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8'
	# 	}
	# 	# URL-encode each value (mimics curl --data-urlencode)
	# 	# urllib.parse.urlencode will percent-encode reserved characters
	# 	encoded_body = urllib.parse.urlencode(data)
	# 	response = request(method="POST", url=self.AUTH_URL, data=encoded_body , headers = headers)
	# 	result = response.json()
	# 	if response.status_code == 200:
	# 		frappe.log_error(title="Amazon SP Token" , message = f"{result}")
	# 		return result.get("access_token")
	# 	exception = SPAPIError(
	# 		error=result.get("error"), error_description=result.get("error_description")
	# 	)
	# 	raise exception

	def get_headers(self) -> dict:
		return {"x-amz-access-token": self.get_access_token()}

	def _mask_headers(headers: dict, hide_keys=("authorization", "x-amz-access-token", "x-amz-security-token")) -> dict:
		"""Return a copy of headers with sensitive values masked for logging."""
		masked = {}
		for k, v in (headers or {}).items():
			lk = k.lower()
			if any(h in lk for h in hide_keys):
				masked[k] = "***MASKED***"
			else:
				masked[k] = v
		return masked

	def make_request(
		self,
		method: str = "GET",
		append_to_base_uri: str = "",
		params: dict = None,
		data: dict = None,
	) -> dict:
		if isinstance(params, dict):
			params = Util.remove_empty(params)
		if isinstance(data, dict):
			data = Util.remove_empty(data)

		url = self.endpoint + self.BASE_URI + append_to_base_uri
		headers = self.get_headers()

		try:
			response = request(
				method=method,
				url=url,
				params=params,
				data=data,
				headers=headers,
				timeout=30,  # optional but safer
			)

			# Log request + response if not 2xx
			if response.status_code < 200 or response.status_code >= 300:
				frappe.log_error(
					title="Amazon SP-API Request Error",
					message=(
						f"METHOD: {method}\n"
						f"URL: {response.url}\n"
						f"Headers: {headers}\n"
						f"Params: {params}\n"
						f"Data: {data}\n\n"
						f"Status: {response.status_code}\n"
						f"Response: {response.text}"
					)
				)
				response.raise_for_status()

			# Store request/response details for logging
			try:
				response_json = response.json()
			except Exception:
				response_json = {"error": "Failed to parse JSON", "text": response.text}
			
			self.last_request_details = {
				"method": method,
				"url": response.url if hasattr(response, 'url') else url,
				"headers": headers,
				"params": params,
				"data": data,
				"status_code": str(response.status_code),
				"response": response_json,
			}
			
			return response_json

		except Exception as e:
			# Capture traceback + partial response (if any)
			body = ""
			if "response" in locals():
				body = f"\nStatus: {response.status_code}\nResponse: {response.text}"
				try:
					response_json = response.json()
				except Exception:
					response_json = {"error": str(e), "text": response.text}
			else:
				response_json = {"error": str(e)}
			
			# Store request/response details even for errors
			self.last_request_details = {
				"method": method,
				"url": url,
				"headers": headers,
				"params": params,
				"data": data,
				"status_code": str(getattr(response, 'status_code', 'N/A')) if "response" in locals() else "N/A",
				"response": response_json,
			}
			
			frappe.log_error(
				title="Amazon SP-API Exception",
				message=(
					f"METHOD: {method}\n"
					f"URL: {url}\n"
					f"Params: {params}\n"
					f"Data: {data}\n\n"
					f"Exception: {str(e)}{body}\n"
					f"Traceback:\n{frappe.get_traceback()}"
				)
			)
			# Re-raise so caller sees failure
			raise

	def list_to_dict(self, key: str, values: list, data: dict) -> None:
		if values and isinstance(values, list):
			for idx in range(len(values)):
				data[f"{key}[{idx}]"] = values[idx]

class Finances(SPAPI):
	""" Amazon Finances API """

	BASE_URI = "/finances/v0/"

	def list_financial_events_by_order_id(
		self, order_id: str, max_results: int = None, next_token: str = None
	) -> dict:
		""" Returns all financial events for the specified order. """
		append_to_base_uri = f"orders/{order_id}/financialEvents"
		data = dict(MaxResultsPerPage=max_results, NextToken=next_token)
		return self.make_request(append_to_base_uri=append_to_base_uri, params=data)
class Orders(SPAPI):
	""" Amazon Orders API """

	BASE_URI = "/orders/v0/orders"

	def get_orders(
		self,
		created_after: str = None,
		created_before: str = None,
		last_updated_after: str = None,
		last_updated_before: str = None,
		order_statuses: list = None,
		marketplace_ids: list = None,
		fulfillment_channels: list = None,
		payment_methods: list = None,
		buyer_email: str = None,
		seller_order_id: str = None,
		max_results: int = 100,
		easyship_shipment_statuses: list = None,
		next_token: str = None,
		amazon_order_ids: str = None,
		actual_fulfillment_supply_source_id: str = None,
		is_ispu: bool = False,
		store_chain_store_id: str = None,
	) -> dict:
		""" Returns orders created or updated during the time frame indicated by the specified parameters. You can also apply a range of filtering criteria to narrow the list of orders returned. If NextToken is present, that will be used to retrieve the orders instead of other criteria. """
		data = dict(
			CreatedAfter=created_after,
			CreatedBefore=created_before,
			LastUpdatedAfter=last_updated_after,
			LastUpdatedBefore=last_updated_before,
			BuyerEmail=buyer_email,
			SellerOrderId=seller_order_id,
			MaxResultsPerPage=max_results,
			NextToken=next_token,
			ActualFulfillmentSupplySourceId=actual_fulfillment_supply_source_id,
			IsISPU=is_ispu,
			StoreChainStoreId=store_chain_store_id,
		)

		self.list_to_dict("OrderStatuses", order_statuses, data)
		self.list_to_dict("MarketplaceIds", marketplace_ids, data)
		self.list_to_dict("FulfillmentChannels", fulfillment_channels, data)
		self.list_to_dict("PaymentMethods", payment_methods, data)
		self.list_to_dict("EasyShipShipmentStatuses", easyship_shipment_statuses, data)
		# self.list_to_dict("AmazonOrderIds", amazon_order_ids, data)

		if not marketplace_ids:
			marketplace_ids = [self.marketplace_id]
			data["MarketplaceIds"] = marketplace_ids

		if amazon_order_ids:
			data['AmazonOrderIds'] = amazon_order_ids

		return self.make_request(params=data)

	def get_order_items(self, order_id: str, next_token: str = None) -> dict:
		""" Returns detailed order item information for the order indicated by the specified order ID. If NextToken is provided, it's used to retrieve the next page of order items. """
		append_to_base_uri = f"/{order_id}/orderItems"
		data = dict(NextToken=next_token)
		return self.make_request(append_to_base_uri=append_to_base_uri, params=data)

	def get_order(self, order_id: str) -> dict:
		""" Method to get a Particular Order """
		append_to_base_uri = f"/{order_id}"
		return self.make_request(append_to_base_uri=append_to_base_uri)

class CatalogItems(SPAPI):
	""" Amazon Catalog Items API """

	BASE_URI = "/catalog/2022-04-01"

	def get_catalog_item(self, asin: str, marketplace_id: str = None,) -> dict:
		""" Returns a specified item and its attributes. """
		if not marketplace_id:
			marketplace_id = self.marketplace_id

		append_to_base_uri = f"/items/{asin}"
		data = dict(marketplaceIds=marketplace_id)

		return self.make_request(append_to_base_uri=append_to_base_uri, params=data)


class Util:
	@staticmethod
	def get_marketplace(country_code):
		for selling_region in MARKETPLACES:
			for country in MARKETPLACES.get(selling_region):
				if country_code == country:
					return MARKETPLACES.get(selling_region)
		else:
			raise KeyError(f"Invalid Country Code: {country_code}")

	@staticmethod
	def get_marketplace_data(country_code):
		marketplace = Util.get_marketplace(country_code)
		region = marketplace.get("AWS Region")
		endpoint = marketplace.get("Endpoint")
		marketplace_id = marketplace.get(country_code)

		return region, endpoint, marketplace_id

	@staticmethod
	def remove_empty(dict):
		"""
		Helper function that removes all keys from a dictionary (dict), that have an empty value.
		"""
		for key in list(dict):
			if not dict[key]:
				del dict[key]
		return dict
