#include <PDM.h>
#include <stefan.marinkovic-project-1_inferencing.h>
#include <ArduinoBLE.h>
#include <Arduino_APDS9960.h>
#include <Arduino_LSM9DS1.h>

BLEService sensorService("180C");

BLECharacteristic sensorChar(
  "2A56",
  BLENotify,
  256
);

#define BLUE_LED LEDB
#define RED_LED LEDR
#define BUTTON_PIN A0
#define DATA_COLLECTION_FREQUENCY 20

typedef struct {
    int16_t *buffer;
    uint8_t buf_ready;
    uint32_t buf_count;
    uint32_t n_samples;
} inference_t;

static inference_t inference;
static signed short sampleBuffer[2048];

bool monitoringActive = false;
bool dataCollecting = false;

static void pdm_data_ready_inference_callback(void)
{
    int bytesAvailable = PDM.available();
    PDM.read((char *)&sampleBuffer[0], bytesAvailable);

    if (inference.buf_ready == 0) {

        for (int i = 0; i < bytesAvailable >> 1; i++) {

            inference.buffer[inference.buf_count++] = sampleBuffer[i];

            if (inference.buf_count >= inference.n_samples) {
                inference.buf_count = 0;
                inference.buf_ready = 1;
                break;
            }
        }
    }
}

static bool microphone_inference_start(uint32_t n_samples)
{
    inference.buffer = (int16_t *)malloc(n_samples * sizeof(int16_t));

    if (!inference.buffer) return false;

    inference.buf_count = 0;
    inference.n_samples = n_samples;
    inference.buf_ready = 0;

    PDM.onReceive(&pdm_data_ready_inference_callback);
    PDM.setBufferSize(4096);

    if (!PDM.begin(1, EI_CLASSIFIER_FREQUENCY)) {
        return false;
    }

    PDM.setGain(127);

    return true;
}

static bool microphone_inference_record(void)
{
    inference.buf_ready = 0;
    inference.buf_count = 0;
    int count = 0;

    while (inference.buf_ready == 0) {
        delay(50);
        if(dataCollecting && count < DATA_COLLECTION_FREQUENCY){
            sendOverBT();
            count++;
        }
    }
    Serial.println(count);
    return true;
}

static int microphone_audio_signal_get_data(size_t offset, size_t length, float *out_ptr)
{
    numpy::int16_to_float(&inference.buffer[offset], out_ptr, length);
    return 0;
}

void runInference()
{
    signal_t signal;
    signal.total_length = EI_CLASSIFIER_RAW_SAMPLE_COUNT;
    signal.get_data = &microphone_audio_signal_get_data;

    ei_impulse_result_t result = { 0 };

    EI_IMPULSE_ERROR r = run_classifier(&signal, &result, false);

    if (r != EI_IMPULSE_OK) return;

    Serial.println("---- inference ----");

    for (size_t i = 0; i < EI_CLASSIFIER_LABEL_COUNT; i++) {

        const char *label = result.classification[i].label;
        float value = result.classification[i].value;

        Serial.print(label);
        Serial.print(": ");
        Serial.println(value);

        if (value < 0.80) continue;

        if (strcmp(label, "monitor") == 0) {
            monitoringActive = true;
        }

        if (strcmp(label, "silence") == 0) {
            monitoringActive = false;
        }

        if (strcmp(label, "begin_data_acquisition") == 0) {
            dataCollecting = true;
        }
    }
}

//initial values of sensors
int proximity = -1;
float ax = 0, ay = 0, az = 0;
float gx = 0, gy = 0, gz = 0;

void sendOverBT(){
    
    // ---------- PROXIMITY ----------

    if (APDS.proximityAvailable()) 
        proximity = APDS.readProximity();

    // ---------- ACCELEROMETER ----------

    if (IMU.accelerationAvailable())
        IMU.readAcceleration(ax, ay, az);

    // ---------- GYROSCOPE ----------

    if (IMU.gyroscopeAvailable())
        IMU.readGyroscope(gx, gy, gz);

    // ---------- BUTTON ----------
    int button = digitalRead(A0) == LOW ? 1 : 0;

    // ---------- BLE PAYLOAD ----------
    char buffer[256];

    snprintf(buffer, sizeof(buffer),
        "Proximity:%d,AccelX:%.8f,AccelY:%.8f,AccelZ:%.8f,GyroX:%.8f,GyroY:%.8f,GyroZ:%.8f,Button:%d,CreatedAt:%d",
        proximity,
        ax, ay, az,
        gx, gy, gz,
        button, millis()
    );

    // ---------- SEND ----------
    sensorChar.writeValue(buffer);

    // ---------- DEBUG ----------
    Serial.println(buffer);
}

void setup()
{
    Serial.begin(115200);

    pinMode(BLUE_LED, OUTPUT);
    pinMode(RED_LED, OUTPUT);

    digitalWrite(BLUE_LED, LOW);
    digitalWrite(RED_LED, LOW);

    if (!microphone_inference_start(EI_CLASSIFIER_RAW_SAMPLE_COUNT)) {
        Serial.println("MIC INIT FAIL");
        while (1);
    }

    if (!BLE.begin()) {
        Serial.println("BLE failed");
        while (1);
    }

    BLE.setLocalName("Nano33-Sensors");
    BLE.setAdvertisedService(sensorService);

    sensorService.addCharacteristic(sensorChar);
    BLE.addService(sensorService);

    sensorChar.writeValue("INIT");

    BLE.advertise();

    if (!APDS.begin())
        Serial.println("Failed to init APDS sensor!");

    if (!IMU.begin())
        Serial.println("IMU failed");
    
    digitalWrite(BLUE_LED, HIGH);
    digitalWrite(RED_LED, HIGH);
}

void loop()
{
    BLE.poll();
    ei_printf("Recording...\n");

    bool ok = microphone_inference_record();
    if (!ok) return;

    ei_printf("Done\n");

    runInference();

    if (!monitoringActive) {
        digitalWrite(BLUE_LED, HIGH);
        digitalWrite(RED_LED, HIGH);
        return;
    }

    digitalWrite(RED_LED, LOW);
    digitalWrite(BLUE_LED, LOW);
}