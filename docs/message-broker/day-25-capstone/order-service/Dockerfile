FROM golang:1.22-alpine AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY shared ./shared
COPY order-service ./order-service
RUN go build -o /out/service ./order-service

FROM alpine:3.19
RUN apk add --no-cache ca-certificates
COPY --from=build /out/service /service
EXPOSE 8080
ENTRYPOINT ["/service"]
