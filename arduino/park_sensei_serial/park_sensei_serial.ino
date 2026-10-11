/*
 * ParkSensei manual-drive firmware for Arduino Uno + Adafruit Motor Shield V1.
 *
 * Serial protocol at 115200 baud, one ASCII command per line:
 *   PING                         -> PONG
 *   MOVE <F|B|L|R> <pwm> <ms>   -> OK MOVE
 *   STOP                         -> OK STOP
 *   ESTOP                        -> OK ESTOP (latched until CLEAR)
 *   CLEAR                        -> OK CLEAR
 *   STATUS                       -> STATUS IDLE|MOVING|ESTOP
 *
 * Motor power must come from the motor supply/shield, not USB. A MOVE is a
 * short lease; it stops automatically after at most 500 ms unless renewed.
 */

#include <AFMotor.h>
#include <stdio.h>
#include <string.h>

AF_DCMotor motor1(1);
AF_DCMotor motor2(2);

const unsigned long MAX_MOVE_MS = 500;
const unsigned long MIN_MOVE_MS = 350;
const size_t LINE_CAPACITY = 48;

// HC-SR04 wired to the Uno's unused analog pins. The Motor Shield V1 uses
// digital pins 3-12, leaving A0/A1 available as digital I/O.
const uint8_t ULTRASONIC_TRIG_PIN = A0;
const uint8_t ULTRASONIC_ECHO_PIN = A1;
const unsigned long SENSOR_SAMPLE_INTERVAL_MS = 70;
const unsigned long SENSOR_ECHO_TIMEOUT_US = 12000UL;
const unsigned int SENSOR_TRIGGER_DISTANCE_CM = 18;
const unsigned int SENSOR_CLEAR_DISTANCE_CM = 26;
const uint8_t SENSOR_CONFIRM_SAMPLES = 2;
const int SENSOR_REVERSE_SPEED = 120;
const unsigned long SENSOR_REVERSE_MS = 250;
const unsigned long SENSOR_COOLDOWN_MS = 1200;

char lineBuffer[LINE_CAPACITY];
size_t lineLength = 0;
bool estopLatched = false;
bool moving = false;
unsigned long stopAt = 0;
unsigned long lastSensorSampleAt = 0;
unsigned long lastSensorActionAt = 0;
uint8_t nearSamples = 0;
uint8_t clearSamples = 0;
bool sensorArmed = true;
bool sensorHasActed = false;

void stopMotors()
{
  motor1.run(RELEASE);
  motor2.run(RELEASE);
  moving = false;
}

unsigned int readDistanceCm()
{
  digitalWrite(ULTRASONIC_TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(ULTRASONIC_TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(ULTRASONIC_TRIG_PIN, LOW);

  const unsigned long echoUs = pulseIn(
      ULTRASONIC_ECHO_PIN, HIGH, SENSOR_ECHO_TIMEOUT_US);
  if (echoUs == 0)
    return 0; // No echo means no nearby obstacle was measured.
  return (unsigned int)(echoUs / 58UL);
}

void checkUltrasonicSensor(unsigned long now)
{
  if ((unsigned long)(now - lastSensorSampleAt) < SENSOR_SAMPLE_INTERVAL_MS)
    return;
  lastSensorSampleAt = now;

  const unsigned int distanceCm = readDistanceCm();
  const bool nearObject = distanceCm > 0 && distanceCm <= SENSOR_TRIGGER_DISTANCE_CM;
  const bool clear = distanceCm == 0 || distanceCm >= SENSOR_CLEAR_DISTANCE_CM;

  if (clear)
  {
    nearSamples = 0;
    if (clearSamples < SENSOR_CONFIRM_SAMPLES)
      clearSamples++;
    if (clearSamples >= SENSOR_CONFIRM_SAMPLES)
      sensorArmed = true;
    return;
  }

  clearSamples = 0;
  if (!nearObject || !sensorArmed)
  {
    nearSamples = 0;
    return;
  }

  // Only trigger from rest. This keeps a hand test from fighting a manual
  // drive command and prevents the sensor from reversing during a turn.
  if (moving || estopLatched)
  {
    nearSamples = 0;
    return;
  }

  if (nearSamples < SENSOR_CONFIRM_SAMPLES)
    nearSamples++;
  const bool cooldownElapsed = !sensorHasActed ||
                               (unsigned long)(now - lastSensorActionAt) >= SENSOR_COOLDOWN_MS;
  if (nearSamples < SENSOR_CONFIRM_SAMPLES || !cooldownElapsed)
    return;

  motor1.setSpeed(SENSOR_REVERSE_SPEED);
  motor2.setSpeed(SENSOR_REVERSE_SPEED);
  motor1.run(BACKWARD);
  motor2.run(BACKWARD);
  moving = true;
  stopAt = now + SENSOR_REVERSE_MS;
  lastSensorActionAt = now;
  sensorHasActed = true;
  sensorArmed = false;
  nearSamples = 0;
}

void beginMove(char direction, int speed, unsigned long durationMs)
{
  if (estopLatched)
  {
    Serial.println("ERR ESTOP");
    return;
  }

  speed = constrain(speed, 0, 255);
  if (speed == 0)
  {
    stopMotors();
    Serial.println("OK STOP");
    return;
  }

  durationMs = constrain(durationMs, MIN_MOVE_MS, MAX_MOVE_MS);
  motor1.setSpeed(speed);
  motor2.setSpeed(speed);

  switch (direction)
  {
  case 'F':
    motor1.run(FORWARD);
    motor2.run(FORWARD);
    break;
  case 'B':
    motor1.run(BACKWARD);
    motor2.run(BACKWARD);
    break;
  case 'L':
    // Motor 1 is the left wheel: hold it and drive the right wheel forward.
    // This avoids counter-rotating both motors against the robot's weight.
    motor1.run(RELEASE);
    motor2.run(FORWARD);
    break;
  case 'R':
    // Motor 2 is the right wheel: hold it and drive the left wheel forward.
    motor1.run(FORWARD);
    motor2.run(RELEASE);
    break;
  default:
    stopMotors();
    Serial.println("ERR DIRECTION");
    return;
  }

  moving = true;
  stopAt = millis() + durationMs;
  Serial.println("OK MOVE");
}

void handleLine(char *line)
{
  if (strcmp(line, "PING") == 0)
  {
    Serial.println("PONG");
    return;
  }

  if (strcmp(line, "STOP") == 0)
  {
    stopMotors();
    Serial.println("OK STOP");
    return;
  }

  if (strcmp(line, "ESTOP") == 0)
  {
    estopLatched = true;
    stopMotors();
    Serial.println("OK ESTOP");
    return;
  }

  if (strcmp(line, "CLEAR") == 0)
  {
    stopMotors();
    estopLatched = false;
    Serial.println("OK CLEAR");
    return;
  }

  if (strcmp(line, "STATUS") == 0)
  {
    if (estopLatched)
      Serial.println("STATUS ESTOP");
    else if (moving)
      Serial.println("STATUS MOVING");
    else
      Serial.println("STATUS IDLE");
    return;
  }

  char direction = 0;
  int speed = 0;
  unsigned long durationMs = 0;
  if (sscanf(line, "MOVE %c %d %lu", &direction, &speed, &durationMs) == 3)
  {
    beginMove(direction, speed, durationMs);
    return;
  }

  Serial.println("ERR COMMAND");
}

void setup()
{
  Serial.begin(115200);
  pinMode(ULTRASONIC_TRIG_PIN, OUTPUT);
  pinMode(ULTRASONIC_ECHO_PIN, INPUT);
  digitalWrite(ULTRASONIC_TRIG_PIN, LOW);
  stopMotors();
  Serial.println("READY");
}

void loop()
{
  while (Serial.available() > 0)
  {
    const char c = (char)Serial.read();
    if (c == '\r')
      continue;
    if (c == '\n')
    {
      lineBuffer[lineLength] = '\0';
      if (lineLength > 0)
        handleLine(lineBuffer);
      lineLength = 0;
    }
    else if (lineLength < LINE_CAPACITY - 1)
    {
      lineBuffer[lineLength++] = c;
    }
    else
    {
      lineLength = 0;
      stopMotors();
      Serial.println("ERR LINE_TOO_LONG");
    }
  }

  // Every movement expires automatically. The HUD renews its short command
  // while a button is held and sends STOP as soon as it is released.
  const unsigned long now = millis();
  if (moving && (long)(now - stopAt) >= 0)
    stopMotors();
  checkUltrasonicSensor(now);
}
