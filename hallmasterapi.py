import re
from pprint import pprint
from typing import Any

import requests
import json
from datetime import datetime, timedelta
from bs4 import BeautifulSoup


class Booking:
	def __init__(
			self,
			id: int,
			title: str,
			start: datetime,
			end: datetime,
			rooms: list[str],
			description: str = "",
	):
		self.id = id
		self.title = title
		self.description = description
		self.start = start
		self.end = end
		self.rooms = rooms

	def __repr__(self):
		return f"""Booking(
	id: {self.id},
	title: '{self.title}',
	start: {self.start},
	end: {self.end},
	rooms: {self.rooms},
	description: '{self.description}'
)"""


class HallmasterAPI:
	version = '0.1.0'

	api_subdomain = "https://v2.hallmaster.co.uk"
	api_time_format = "%Y-%m-%dT%H:%M:%S+00:00"  # note: tz addon as %z not currently working for datetime.now(), assume UTC
	api_user_agent = f"Hallmaster Python API v{version}"

	def __init__(self, hall_id: int):
		self.hall_id = hall_id
		self.rooms_info = self.get_rooms_info()

	def format_date(self, date: datetime) -> str:
		return date.strftime(self.api_time_format)

	def get_rooms_info(self) -> dict[str, dict]:
		html = requests.get(
			f"{self.api_subdomain}/Scheduler/View/{self.hall_id}",
			headers={'user-agent': self.api_user_agent}
		)
		soup = BeautifulSoup(html.content, "html.parser")
		colour_list = soup.find(id="RoomColorList")
		rooms_info = {}
		for div in colour_list.find_all(onclick=True):
			room_id = int(re.findall(r"setRoom\((\d+)\)", div["onclick"])[0])
			colour = re.findall(r"background-color:(#[a-fA-F0-9]+)!important;", div["style"])[0]
			rooms_info[colour] = {"id": room_id, "name": div.text, "colour": colour}

		return rooms_info

	def get_bookings(self,
		start_date: datetime,
		end_date: datetime,
		room_id: int = 0,
		get_desc: bool = False) \
		-> list[Booking]:

		params = {
			"roomId": room_id,
			"custView": False,
			"HallId": self.hall_id,
			"start": self.format_date(start_date),
			"end": self.format_date(end_date)
		}

		raw_bookings = requests.get(
			f"{self.api_subdomain}/api/Scheduler/GetBookings",
			params=params,
			headers={'user-agent': self.api_user_agent}
		)

		bookings = json.loads(raw_bookings.content)

		collated_entries = {}
		for booking in bookings:
			if booking["title"] not in ["Private Booking", "Provisional Booking"]:
				key = (booking["title"], booking["start"], booking["end"])
				room = self.rooms_info[booking['color']]["name"]

				value = Booking(
					id=booking["Id"],
					title=booking["title"],
					start=booking["start"],
					end=booking["end"],
					rooms=[room],
				)

				if get_desc:
					value.description = self.get_description(value.id)

				if key in collated_entries.keys():
					collated_entries[key].rooms.append(room)
				else:
					collated_entries[key] = value

		return list(collated_entries.values())

	def search(self, search_terms: str | list[str], start_date: datetime, end_date: datetime, room_id: int = 0) -> list[Booking]:
		bookings = self.get_bookings(start_date, end_date, room_id)
		if type(search_terms) is str:
			search_terms = [search_terms]

		confident_matches = []
		somewhat_sure_matches = []

		for term in search_terms:
			# Extract acronym from search query
			acronym = ''.join(re.findall(r'\b\w', term)).upper()

			for item in bookings:
				title = item.title

				# Check if the search query is an exact match or very close
				if term.lower() in title.lower():
					item.description = self.get_description(item.id)
					confident_matches.append(item)
				else:
					# If not confident, get the description and search within it
					if not item.description:
						item.description = self.get_description(item.id)

					# Check if the search query is a match within the description
					if term.lower() in item.description.lower():
						somewhat_sure_matches.append(item)

					# Check if acronym is a match in the title
					if acronym.lower() in title.lower():
						confident_matches.append(item)
						break
					# Check if acronym is a match in the description
					if acronym.lower() in item.description.lower():
						somewhat_sure_matches.append(item)
						break

		return confident_matches + somewhat_sure_matches

	def get_description(self, booking_id: int) -> str:
		html = requests.get(
			f"{self.api_subdomain}/Scheduler/ViewBooking/{booking_id}",
			headers={'user-agent': self.api_user_agent}
		)
		soup = BeautifulSoup(html.content, "html.parser")
		if desc := soup.find(attrs={"for": "Description"}):
			return desc.parent.div.text.strip()
		else:
			return " "


if __name__ == '__main__':
	api = HallmasterAPI(hall_id=11119)
	print(api.rooms_info)
	api.get_bookings(datetime.now(), datetime.now()+timedelta(days=90))
