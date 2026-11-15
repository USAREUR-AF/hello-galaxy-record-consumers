# The decoder at the edge: the published first-bite image, with this example's
# dictionary and sample capture added. Nothing is compiled.
#
# The base is first-bite's release candidate v1.0.1-rc.1 by digest; FIRST_BITE_IMAGE
# at the repository root is where the pin lives, and bin/hello-consumers build
# passes it in.
ARG FIRST_BITE_IMAGE
FROM ${FIRST_BITE_IMAGE}
COPY dictionaries/harbour-buoy /dictionary
COPY examples/harbour-buoys.pcap /examples/harbour-buoys.pcap
